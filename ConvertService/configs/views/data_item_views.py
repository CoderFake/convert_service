import json
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction, IntegrityError
from django.db.models import Q, F, Subquery, IntegerField, OuterRef, Max
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views import View
from django.db.models.functions import Cast

from home.models import DataItem, FileFormat, DataFormat, DataItemType, DetailedInfo

import logging

logger = logging.getLogger(__name__)


class DataItemListView(LoginRequiredMixin, View):
    def get(self, request):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return self.get_datatable_data(request)
        else:
            return self.render_page(request)

    def render_page(self, request):
        file_formats = [
            ('CSV', 'CSV'),
            ('EXCEL', 'EXCEL')
        ]

        data_item_type_choices = [
            ('input', '変換前のデータ'),
            ('format', '画面のデータ'),
            ('output', '健診システム取り込みデータ'),
            ('input', '予約代行業者取り込みデータ'),
        ]
        data_type_choices = DataItemType.FormatValue.choices
        data_type_name_choices = DataItemType.TypeName.choices

        context = {
            'file_formats': file_formats,
            "data_type_choices": data_type_choices,
            "data_type_names": data_type_name_choices,
            'data_item_type_choices': data_item_type_choices
        }
        return render(request, 'web/settings/data-item.html', context)

    def get_datatable_data(self, request):
        try:
            tenant = request.user.tenant
            draw = int(request.GET.get('draw', 1))
            start = int(request.GET.get('start', 0))
            length = int(request.GET.get('length', 10))
            search_value = request.GET.get('search[value]', '')
            file_format_id = request.GET.get('file_format_id', '')
            data_type_name = request.GET.get('data_type_name', DataItemType.TypeName.FORMAT)

            base_queryset = DataItem.objects.filter(tenant=tenant)

            if file_format_id:
                base_queryset = base_queryset.filter(data_format__file_format__file_format_id__contains=file_format_id)

            base_queryset = base_queryset.filter(
                data_item_types__type_name=data_type_name
            ).select_related(
                'data_format__file_format'
            ).prefetch_related(
                'data_item_types'
            )

            if search_value:
                base_queryset = base_queryset.filter(
                    Q(data_item_id__icontains=search_value) |
                    Q(data_item_name__icontains=search_value)
                )

            total_records = DataItem.objects.filter(tenant=tenant).count()
            records_filtered = base_queryset.distinct().count()

            item_types_dict = {}
            for item_type in DataItemType.objects.filter(
                    data_item__in=base_queryset,
                    type_name=data_type_name
            ).select_related('data_item'):
                item_types_dict[item_type.data_item_id] = item_type

            unique_ids = list(base_queryset.values(
                'id',
                'data_item_id',
                'data_format__file_format__file_format_id'
            ).distinct())

            sorted_ids = sorted(
                unique_ids,
                key=lambda x: (
                    item_types_dict.get(x['data_item_id'], DataItemType()).index_value or 0,
                    x['id']
                )
            )

            if int(length) == -1:
                paginated_data = sorted_ids
            else:
                paginated_data = sorted_ids[start:start + length]

            paginated_ids = [item['id'] for item in paginated_data]

            paginated_items = list(
                DataItem.objects.filter(id__in=paginated_ids).select_related('data_format__file_format'))

            item_types = {}
            for item_type in DataItemType.objects.filter(
                    data_item__in=paginated_items,
                    type_name=data_type_name
            ).select_related('data_item'):
                item_types[item_type.data_item.id] = item_type

            id_dict = {item.id: item for item in paginated_items}

            ordered_items = [id_dict[id] for id in paginated_ids if id in id_dict]

            format_value_dict = dict(DataItemType.FormatValue.choices)

            data = []
            for index, item in enumerate(ordered_items, start=start + 1):
                item_type = item_types.get(item.id)
                display = item_type.display if item_type else False
                edit_value = item_type.edit_value if item_type else False
                index_value = item_type.index_value if item_type else 0

                format_value_code = item_type.format_value if item_type else 'string'
                format_value_label = format_value_dict.get(format_value_code, '文字列')

                file_format_name = item.data_format.file_format.file_format_name

                data.append({
                    'DT_RowId': f'row_{item.id}',
                    'no': index,
                    'id': item.id,
                    'data_item_id': item.data_item_id,
                    'data_item_name': item.data_item_name,
                    'file_format_name': file_format_name,
                    'display': display,
                    'edit_value': edit_value,
                    'index_value': index_value,
                    'format_value': format_value_code,
                    'format_value_label': format_value_label
                })

            response = {
                'draw': draw,
                'recordsTotal': total_records,
                'recordsFiltered': records_filtered,
                'data': data,
                'file_format_id': file_format_id,
                'data_type_name': data_type_name,
            }
            return JsonResponse(response)

        except Exception as e:
            logger.error(f"Error in get_datatable_data: {str(e)}", exc_info=True)
            return JsonResponse({
                'draw': int(request.GET.get('draw', 1)),
                'recordsTotal': 0,
                'recordsFiltered': 0,
                'data': [],
                'error': str(e)
            })


class DataItemCreateView(LoginRequiredMixin, View):
    def post(self, request):
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request type'}, status=400)

        tenant = request.user.tenant
        data_item_name = request.POST.get('data_item_name')
        index_value = request.POST.get('index_value')
        format_value = request.POST.get('format_value')
        data_type_name = request.POST.get('data_type_name')
        file_format_id = request.POST.get('file_format_id')
        display = request.POST.get('display', "off")
        edit_value= request.POST.get('edit_value', "off")

        errors = {}
        if not data_item_name or not index_value or not format_value or not file_format_id or not data_type_name:
            if not data_item_name:
                errors['data_item_name'] = 'このフィールドは必須です。'
            if not index_value:
                errors['index_value'] = 'このフィールドは必須です。'
            if not format_value or format_value not in [fm for fm in DataItemType.FormatValue.values]:
                errors['format_value'] = 'このフィールドは必須です。'
            if not data_type_name or data_type_name not in [type_name for type_name in DataItemType.TypeName.values]:
                errors['data_type_name'] = 'このフィールドは必須です。'

            return JsonResponse({
                'status': 'error',
                'errors': errors,
            }, status=200)

        try:
            if int(index_value) < 0:
                errors["index_value"] = "値は負の数にできません。"
        except ValueError:
            errors["index_value"] = "数値を入力してください。"

        if errors != {}:
            return JsonResponse({
                'status': 'error',
                'errors': errors,
            }, status=200)


        data_item = DataItem.objects.filter(
            data_item_name=data_item_name,
            data_format__file_format__file_format_id__contains=file_format_id,
        ).first()

        if data_item:
            errors['data_item_name'] = '列名は既に存在します'

        if DataItemType.objects.filter(
            type_name=data_type_name,
            index_value=index_value
        ).first():
            errors['index_value'] = '位置はすでに存在しています'

        if errors != {}:
            return JsonResponse({
                'status': 'error',
                'errors': errors,
            }, status=200)

        try:
            with transaction.atomic():
                from django.db.models import Max, Subquery, OuterRef, IntegerField
                from django.db.models.functions import Cast
                last_data_item = DataItem.objects.order_by('-id').first()

                data_item_id = f"D000{int(last_data_item.data_item_id.split('D000')[1]) + 1}"

                data_format = DataFormat.objects.filter(
                    file_format__file_format_id__contains=file_format_id,
                    tenant=tenant,
                ).first()

                data_item = DataItem.objects.create(
                    tenant=tenant,
                    data_format=data_format,
                    data_item_id=data_item_id,
                    data_item_name=data_item_name
                )

                display_val = True if display == 'on' else False
                edit_val = True if edit_value == 'on' else False

                DataItemType.objects.create(
                    data_item=data_item,
                    type_name=data_type_name,
                    index_value=index_value,
                    display=display_val,
                    edit_value=edit_val,
                    format_value=format_value,
                )

                return JsonResponse({
                    'status': 'success',
                    'message': f'データ項目「{data_item_name}」が正常に作成されました。'
                })

        except Exception as e:
            logger.error(f"Error in create_datatable_data: {str(e)}", exc_info=True)
            return JsonResponse({}, status=200)


class DataItemEditView(LoginRequiredMixin, View):
    def post(self, request, item_id):
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request type'}, status=400)

        tenant = request.user.tenant
        data_item_name = request.POST.get('data_item_name')
        index_value = request.POST.get('index_value')
        format_value = request.POST.get('format_value')
        data_type_name = request.POST.get('data_type_name')
        file_format_id = request.POST.get('file_format_id')
        display = request.POST.get('display', "off")
        edit_value = request.POST.get('edit_value', "off")

        errors = {}
        if not data_item_name or not index_value or not format_value or not file_format_id or not data_type_name:
            if not data_item_name:
                errors['data_item_name'] = 'このフィールドは必須です。'
            if not index_value:
                errors['index_value'] = 'このフィールドは必須です。'
            if not format_value or format_value not in [fm for fm in DataItemType.FormatValue.values]:
                errors['format_value'] = 'このフィールドは必須です。'
            if not data_type_name or data_type_name not in [type_name for type_name in DataItemType.TypeName.values]:
                errors['data_type_name'] = 'このフィールドは必須です。'

            return JsonResponse({
                'status': 'error',
                'errors': errors,
            }, status=200)

        try:
            if int(index_value) < 0:
                errors["index_value"] = "値は負の数にできません。"
        except ValueError:
            errors["index_value"] = "数値を入力してください。"

        if errors != {}:
            return JsonResponse({
                'status': 'error',
                'errors': errors,
            }, status=200)

        try:
            with transaction.atomic():
                data_item = get_object_or_404(DataItem, id=item_id, tenant=tenant)

                if DataItem.objects.filter(
                    data_item_name=data_item_name,
                    data_format__file_format__file_format_id__contains=file_format_id,
                ).exclude(id=item_id).exists():
                    errors['data_item_name'] = '列名は既に存在します。'

                duplicate_index = DataItemType.objects.filter(
                    type_name=data_type_name,
                    index_value=index_value,
                    data_item__data_format__file_format__id__contains=file_format_id,
                ).exclude(data_item=data_item)

                if duplicate_index.exists():
                    errors['index_value'] = '位置はすでに存在しています。'

                if errors != {}:
                    return JsonResponse({
                        'status': 'error',
                        'errors': errors,
                    }, status=200)

                data_format = DataFormat.objects.filter(
                    file_format__file_format_id__contains=file_format_id,
                    tenant=tenant,
                ).first()

                data_item.data_item_name = data_item_name
                data_item.data_format = data_format
                data_item.save()

                display_val = True if display == 'on' else False
                edit_val = True if edit_value == 'on' else False

                item_type, _ = DataItemType.objects.get_or_create(
                    data_item=data_item,
                    type_name=data_type_name,
                    defaults={
                        'index_value': index_value,
                        'display': display_val,
                        'edit_value': edit_val,
                        'format_value': format_value,
                    }
                )

                item_type.index_value = index_value
                item_type.display = display_val
                item_type.edit_value = edit_val
                item_type.format_value = format_value
                item_type.save()

                return JsonResponse({
                    'status': 'success',
                    'message': f'データ項目「{data_item_name}」が正常に更新されました。'
                })

        except Exception as e:
            logger.error(f"Error in update_datatable_data: {str(e)}", exc_info=True)
            return JsonResponse({}, status=200)


class DataItemDetailView(LoginRequiredMixin, View):
    def get(self, request, item_id, file_format_id, data_item_type_name):
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request type'}, status=400)

        tenant = request.user.tenant
        try:
            data_item_obj = DataItem.objects.filter(
                tenant=tenant,
                id=item_id,
                data_format__file_format__file_format_id__contains=file_format_id
            ).first()

            data_item = DataItemType.objects.filter(
                data_item=data_item_obj,
                type_name=data_item_type_name
            ).values(
                'data_item_id',
                'data_item__data_item_name',
                'data_item__data_format_id',
                'type_name',
                'index_value',
                'display',
                'edit_value',
                'format_value',
            ).first()

            if not data_item:
                return JsonResponse({
                    'status': 'error',
                    'message': 'データ項目が見つかりませんでした。'
                }, status=404)

            data_item_data = {
                'id': data_item['data_item_id'],
                'data_item_id': data_item['data_item_id'],
                'data_item_name': data_item['data_item__data_item_name'],
                'data_format_id': data_item['data_item__data_format_id'],
                'type_name': data_item['type_name'],
                'index_value': data_item['index_value'],
                'display': data_item['display'],
                'edit_value': data_item['edit_value'],
                'format_value': data_item['format_value'],
            }

            return JsonResponse({
                'status': 'success',
                'data_item': data_item_data,
            })

        except Exception as e:
            logger.error(f"Error fetching DataItem: {e}")
            return JsonResponse({
                'status': 'error',
                'message': f'予期しないエラーが発生しました: {str(e)}'
            }, status=500)


class DataItemDeleteView(LoginRequiredMixin, View):
    def post(self, request, item_id, file_format_id, data_item_type_name):
        try:
            tenant = request.user.tenant
            data_item = get_object_or_404(
                DataItem,
                id=item_id,
                tenant=tenant,
                data_format__file_format__file_format_id__contains=file_format_id
            )

            with transaction.atomic():
                data_item_type = DataItemType.objects.filter(
                    data_item=data_item, type_name=data_item_type_name
                )
                DetailedInfo.objects.filter(
                    Q(data_item_type_before__in=data_item_type) |
                    Q(data_item_type_after__in=data_item_type)
                ).delete()
                data_item_type.delete()

                if not DataItemType.objects.filter(data_item=data_item).exists():
                    data_item.delete()

            return JsonResponse({'status': 'success'})
        except Exception as e:
            logger.error(f"Delete error: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)})


class DataItemTypeUpdateView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            data_item_id = request.POST.get('data_item_id')
            type_name = request.POST.get('type_name')
            field = request.POST.get('field')
            value = request.POST.get('value')

            data_item = get_object_or_404(DataItem, id=data_item_id, tenant=request.user.tenant)
            data_item_type, created = DataItemType.objects.get_or_create(
                data_item=data_item,
                type_name=type_name
            )
            if field == 'display' or field == 'edit_value':
                setattr(data_item_type, field, value == 'true')
            elif field == 'index_value':
                setattr(data_item_type, field, int(value))
            else:
                setattr(data_item_type, field, value)

            data_item_type.save()

            return JsonResponse({'status': 'success'})

        except Exception as e:
            logger.error(f"Lỗi khi cập nhật DataItemType: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)})
