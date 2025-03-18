from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views import View
from configs.models import ConvertRule, ConvertDataValue
from home.models import FileFormat, DataItemType, DataItem, DetailedInfo, DataConversionInfo, DataFormat
from configs.utils import remove_bom

class ConfigsView(LoginRequiredMixin, View):
    def get(self, request):
        format_list = list(FileFormat.objects.all())
        return render(request, 'web/settings/index.html', {'format_list': format_list})


class RuleSettingsView(LoginRequiredMixin, View):
    def get(self, request):
        try:
            tenant = request.user.tenant

            # Lấy các data item đầu vào
            data_inputs = DataItem.objects.filter(
                tenant=tenant,
                data_format__data_format_id="DF_003",
                data_item_types__type_name='input'
            ).select_related(
                'data_format'
            ).prefetch_related(
                'data_item_types'
            ).order_by('data_item_types__index_value')

            # Lấy format/output data items
            data_formats = DataItem.objects.filter(
                tenant=tenant,
                data_format__data_format_id="DF_003",
                data_item_types__type_name='format'
            ).select_related(
                'data_format'
            ).prefetch_related(
                'data_item_types'
            ).order_by('data_item_types__index_value')

            # Lấy tất cả convert rules
            rules = ConvertRule.objects.all().select_related('convert_rule_category')

            # Lấy tất cả các rule đã tồn tại cho tenant này
            data_convert = DataConversionInfo.objects.filter(tenant=tenant).first()
            existing_rules = []

            if data_convert:
                detailed_infos = DetailedInfo.objects.filter(
                    tenant=tenant,
                    data_convert=data_convert
                ).select_related(
                    'data_item_type_id_before__data_item',
                    'data_item_type_id_after__data_item',
                    'convert_rule',
                    'convert_rule__convert_rule_category'
                )

                for info in detailed_infos:
                    existing_rules.append({
                        'id': info.id,
                        'input_item': info.data_item_type_id_before.data_item.data_item_name,
                        'output_item': info.data_item_type_id_after.data_item.data_item_name,
                        'rule_name': info.convert_rule.convert_rule_name,
                        'rule_category': info.convert_rule.convert_rule_category.convert_rule_category_name,
                    })

            # Lấy tất cả các giá trị dữ liệu cố định
            fixed_data_values = ConvertDataValue.objects.filter(
                tenant=tenant
            ).select_related('convert_rule')

            # Lấy tất cả các header setting
            headers = DataItemType.objects.filter(
                data_item__tenant=tenant,
                data_item__data_format__data_format_id="DF_003"
            ).select_related('data_item')

            context = {
                'data_inputs': data_inputs,
                'data_formats': data_formats,
                'rules': rules,
                'existing_rules': existing_rules,
                'fixed_data_values': fixed_data_values,
                'headers': headers
            }

            return render(request, 'web/settings/rule_settings.html', context)
        except Exception as e:
            messages.error(request, f"Đã xảy ra lỗi: {str(e)}")
            return redirect('home')

    def post(self, request):
        try:
            with transaction.atomic():
                tenant = request.user.tenant
                rule_id = request.POST.get("rule_name")
                data_item_input_id = request.POST.get("data_item_input")
                data_item_format_id = request.POST.get("data_item_format")

                # Kiểm tra và lấy các đối tượng
                rule = ConvertRule.objects.get(id=rule_id)
                data_item_input = DataItem.objects.get(id=data_item_input_id, tenant=tenant)
                data_item_format = DataItem.objects.get(id=data_item_format_id, tenant=tenant)
                data_convert = DataConversionInfo.objects.filter(
                    tenant=tenant,
                    data_convert_id="C_001"
                ).first()

                if not data_convert:
                    messages.error(request, "Không tìm thấy thông tin chuyển đổi dữ liệu.")
                    return redirect('rule_settings')

                # Lấy data_item_type
                data_item_type_before = DataItemType.objects.get(
                    data_item=data_item_input,
                    type_name='input'
                )

                data_item_type_after = DataItemType.objects.get(
                    data_item=data_item_format,
                    type_name='format'
                )

                # Kiểm tra xem rule đã tồn tại chưa
                detail_info = DetailedInfo.objects.filter(
                    tenant=tenant,
                    data_convert=data_convert,
                    data_item_type_id_before=data_item_type_before,
                    data_item_type_id_after=data_item_type_after,
                ).first()

                if detail_info:
                    detail_info.convert_rule = rule
                    detail_info.save()
                    messages.success(request, "Cập nhật rule thành công!")
                else:
                    # Tạo rule mới
                    DetailedInfo.objects.create(
                        tenant=tenant,
                        data_convert=data_convert,
                        data_item_type_id_before=data_item_type_before,
                        data_item_type_id_after=data_item_type_after,
                        convert_rule=rule,
                    )
                    messages.success(request, "Thêm rule mới thành công!")

                return redirect('rule_settings')

        except Exception as e:
            messages.error(request, f"Đã xảy ra lỗi: {str(e)}")
            return redirect('rule_settings')


class AddFixedDataView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            rule_id = request.POST.get('rule')
            before_value = request.POST.get('before')
            after_value = request.POST.get('after')

            if not rule_id or not before_value or not after_value:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Thiếu thông tin cần thiết'
                })

            # Lấy ConvertRule
            convert_rule = ConvertRule.objects.filter(convert_rule_id=rule_id).first()
            if not convert_rule:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Không tìm thấy rule'
                })

            # Kiểm tra xem đã tồn tại chưa
            existing = ConvertDataValue.objects.filter(
                tenant=request.user.tenant,
                convert_rule=convert_rule,
                data_value_before=before_value
            ).first()

            if existing:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Giá trị này đã tồn tại'
                })

            # Thêm mới
            fixed_data = ConvertDataValue.objects.create(
                tenant=request.user.tenant,
                convert_rule=convert_rule,
                data_value_before=before_value,
                data_value_after=after_value
            )

            return JsonResponse({
                'status': 'success',
                'id': fixed_data.id,
                'rule_name': convert_rule.convert_rule_name
            })

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Đã xảy ra lỗi: {str(e)}'
            })


class DeleteFixedDataView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            fixed_data_id = request.POST.get('id')

            if not fixed_data_id:
                return JsonResponse({
                    'status': 'error',
                    'message': 'ID không hợp lệ'
                })

            # Tìm và xóa
            fixed_data = ConvertDataValue.objects.filter(
                id=fixed_data_id,
                tenant=request.user.tenant
            ).first()

            if not fixed_data:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Không tìm thấy dữ liệu cần xóa'
                })

            fixed_data.delete()

            return JsonResponse({
                'status': 'success',
                'message': 'Xóa thành công'
            })

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Đã xảy ra lỗi: {str(e)}'
            })


class DeleteRuleView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            rule_id = request.POST.get('rule_id')

            if not rule_id:
                return JsonResponse({
                    'status': 'error',
                    'message': 'ID không hợp lệ'
                })

            # Tìm và xóa
            detailed_info = DetailedInfo.objects.filter(
                id=rule_id,
                tenant=request.user.tenant
            ).first()

            if not detailed_info:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Không tìm thấy rule cần xóa'
                })

            detailed_info.delete()

            return JsonResponse({
                'status': 'success',
                'message': 'Xóa rule thành công'
            })

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Đã xảy ra lỗi: {str(e)}'
            })


class SaveDataItemView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            data = request.POST

            data_format = DataFormat.objects.filter(tenant=request.user.tenant, data_format_id="DF_003").first()
            if not data_format:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Không tìm thấy data format'
                })

            data_list = {}
            for key in data.keys():
                try:
                    if key.startswith('input') or key.startswith('format') or key.startswith('output'):
                        header_name = remove_bom(key.split('[')[1].split(']')[0])
                        field_type = key.split('[')[0]
                        format_key = remove_bom(key)
                        data_list[format_key] = data.get(key)

                        data_item, created = DataItem.objects.get_or_create(
                            data_format=data_format,
                            tenant=request.user.tenant,
                            data_item_name=header_name,
                        )

                        if created:
                            data_item.data_item_id = f"D000{DataItem.objects.count() + 1}"
                            data_item.save()

                        data_item_type, _ = DataItemType.objects.update_or_create(
                            data_item=data_item,
                            type_name=field_type
                        )
                except Exception as e:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Lỗi xử lý khóa {key}: {str(e)}'
                    })

            data_item_types = DataItemType.objects.filter(
                data_item__tenant=request.user.tenant,
                data_item__data_format=data_format
            )

            for data_item_type in data_item_types:
                header_name = data_item_type.data_item.data_item_name
                if data_item_type.type_name == 'input':
                    data_item_type.index_value = int(data_list.get(f"input[{header_name}][index]", "0"))
                    data_item_type.display = bool(int(data_list.get(f"input[{header_name}][display]", "0")))
                    data_item_type.edit_value = bool(int(data_list.get(f"input[{header_name}][edit]", "0")))
                    data_item_type.format_value = data_list.get(f"input[{header_name}][type]", "string")
                elif data_item_type.type_name == 'format':
                    data_item_type.index_value = int(data_list.get(f"format[{header_name}][index]", "0"))
                    data_item_type.display = bool(int(data_list.get(f"format[{header_name}][display]", "0")))
                    data_item_type.edit_value = bool(int(data_list.get(f"format[{header_name}][edit]", "0")))
                    data_item_type.format_value = data_list.get(f"format[{header_name}][type]", "string")
                elif data_item_type.type_name == 'output':
                    data_item_type.index_value = int(data_list.get(f"output[{header_name}][index]", "0"))
                    data_item_type.display = bool(int(data_list.get(f"output[{header_name}][display]", "0")))
                    data_item_type.edit_value = bool(int(data_list.get(f"output[{header_name}][edit]", "0")))
                    data_item_type.format_value = data_list.get(f"output[{header_name}][type]", "string")

                try:
                    data_item_type.save()
                except Exception as e:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Lỗi lưu data_item_type: {str(e)}'
                    })

            return JsonResponse({
                "status": "success",
                "message": "Dữ liệu đã được lưu thành công!"
            })

        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": f"Đã xảy ra lỗi: {str(e)}"
            })


class SaveHeaderSettingsView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            with transaction.atomic():
                data = request.POST

                # Xử lý các cài đặt header
                for key, value in data.items():
                    if key.startswith('display_') or key.startswith('edit_') or key.startswith(
                            'format_') or key.startswith('index_'):
                        parts = key.split('_')
                        prefix = parts[0]
                        header_id = parts[1]

                        # Lấy header item
                        header = DataItemType.objects.filter(
                            id=header_id,
                            data_item__tenant=request.user.tenant
                        ).first()

                        if header:
                            if prefix == 'display':
                                header.display = (value == 'on')
                            elif prefix == 'edit':
                                header.edit_value = (value == 'on')
                            elif prefix == 'format':
                                header.format_value = value
                            elif prefix == 'index':
                                if value.isdigit():
                                    header.index_value = int(value)

                            header.save()

                return JsonResponse({
                    'status': 'success',
                    'message': 'Cài đặt header đã được lưu'
                })

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Đã xảy ra lỗi: {str(e)}'
            })