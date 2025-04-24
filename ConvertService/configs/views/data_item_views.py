from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views import View

from configs.data_type import Mess
from home.models import DataItem, DataItemType, DetailedInfo, DataConversionInfo

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

        data_type_choices = DataItemType.FormatValue.choices
        data_type_name_choices = DataItemType.TypeName.choices

        context = {
            'file_formats': file_formats,
            "data_type_choices": data_type_choices,
            "data_type_names": data_type_name_choices
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
            data_type_name = request.GET.get('data_type_name', DataItemType.TypeName.DISPLAY.value)

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
                    Q(
                        data_item_types__index_value__icontains=search_value,
                        data_item_types__type_name=data_type_name
                    ) | Q(data_item_name__icontains=search_value)
                ).distinct()

            total_records = DataItem.objects.filter(tenant=tenant).count()
            records_filtered = base_queryset.distinct().count()

            item_types = DataItemType.objects.filter(
                data_item__tenant=tenant,
                type_name=data_type_name
            ).select_related('data_item')

            item_types_dict = {}
            for item_type in item_types:
                item_types_dict[item_type.data_item.data_item_id] = item_type.index_value

            items = list(base_queryset.values(
                'id',
                'data_item_id',
                'data_item_name',
                'data_format__file_format__file_format_id',
                'data_format__file_format__file_format_name'
            ).distinct())

            sorted_items = sorted(
                items,
                key=lambda x: (
                    item_types_dict.get(x['data_item_id'], float('inf'))
                )
            )

            if int(length) == -1:
                paginated_items = sorted_items
            else:
                paginated_items = sorted_items[start:start + length]

            paginated_item_ids = [item['data_item_id'] for item in paginated_items]
            item_types_for_paginated = DataItemType.objects.filter(
                data_item__data_item_id__in=paginated_item_ids,
                type_name=data_type_name
            ).select_related('data_item')

            item_type_info = {}
            for item_type in item_types_for_paginated:
                item_type_info[item_type.data_item.data_item_id] = {
                    'display': item_type.display,
                    'edit_value': item_type.edit_value,
                    'index_value': item_type.index_value,
                    'format_value': item_type.format_value
                }

            format_value_dict = dict(DataItemType.FormatValue.choices)

            data = []
            for index, item in enumerate(paginated_items, start=start + 1):
                item_id = item['data_item_id']
                info = item_type_info.get(item_id, {})

                format_value_code = info.get('format_value', 'string')
                format_value_label = format_value_dict.get(format_value_code, '文字列')

                data.append({
                    'DT_RowId': f'row_{item["id"]}',
                    'no': index,
                    'id': item['id'],
                    'data_item_id': item_id,
                    'data_item_name': item['data_item_name'],
                    'file_format_name': item['data_format__file_format__file_format_name'],
                    'display': info.get('display', False),
                    'edit_value': info.get('edit_value', False),
                    'index_value': info.get('index_value', 0),
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
                errors['data_item_name'] = Mess.ERROR_REQUIRED.value
            if not index_value:
                errors['index_value'] = Mess.ERROR_REQUIRED.value
            if not format_value or format_value not in [fm for fm in DataItemType.FormatValue.values]:
                errors['format_value'] = Mess.ERROR_REQUIRED.value
            if not data_type_name or data_type_name not in [type_name for type_name in DataItemType.TypeName.values]:
                errors['data_type_name'] = Mess.ERROR_REQUIRED.value

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
            data_item_types__type_name=data_type_name
        ).first()

        if data_item:
            errors['data_item_name'] = Mess.ERROR_EXIST.value

        if DataItemType.objects.filter(
            type_name=data_type_name,
            index_value=index_value,
            data_item__data_format__file_format__file_format_id__contains=file_format_id,
        ).first():
            errors['index_value'] = Mess.ERROR_EXIST.value

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

                data_convert = DataConversionInfo.objects.filter(
                    data_format_before__file_format__file_format_id__contains=file_format_id,
                    tenant=tenant,
                ).first()

                display_val = True if display == 'on' else False
                edit_val = True if edit_value == 'on' else False

                data_item = DataItem.objects.filter(
                    data_item_name=data_item_name,
                    tenant=tenant,
                    data_format=data_convert.data_format_before,
                ).first()

                if data_item:
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
                        'message': Mess.CREATE.value
                    })

                data_item = DataItem.objects.create(
                    tenant=tenant,
                    data_format=data_convert.data_format_before,
                    data_item_id=data_item_id,
                    data_item_name=data_item_name
                )

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
                    'message': Mess.CREATE.value
                })

        except Exception as e:
            logger.error(f"Error in create_datatable_data: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': Mess.ERROR.value
            }, status=500)


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
                errors['data_item_name'] = Mess.ERROR_REQUIRED.value
            if not index_value:
                errors['index_value'] =  Mess.ERROR_REQUIRED.value
            if not format_value or format_value not in [fm for fm in DataItemType.FormatValue.values]:
                errors['format_value'] =  Mess.ERROR_REQUIRED.value
            if not data_type_name or data_type_name not in [type_name for type_name in DataItemType.TypeName.values]:
                errors['data_type_name'] = Mess.ERROR_REQUIRED.value

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

                data_convert = DataConversionInfo.objects.filter(
                    data_format_before__file_format__file_format_id__contains=file_format_id,
                    tenant=tenant,
                ).first()

                if DataItem.objects.filter(
                    data_item_name=data_item_name,
                    data_format=data_convert.data_format_before,
                    data_item_types__type_name=data_type_name
                ).exclude(id=item_id).exists():
                    errors['data_item_name'] = Mess.ERROR_EXIST.value

                duplicate_index = DataItemType.objects.filter(
                    type_name=data_type_name,
                    index_value=index_value,
                    data_item__data_format=data_convert.data_format_before,
                ).exclude(data_item=data_item)

                if duplicate_index.exists():
                    errors['index_value'] = Mess.ERROR_EXIST.value

                if errors != {}:
                    return JsonResponse({
                        'status': 'error',
                        'errors': errors,
                    }, status=200)

                display_val = True if display == 'on' else False
                edit_val = True if edit_value == 'on' else False

                item_type = get_object_or_404(
                    DataItemType,
                    data_item=data_item,
                    type_name = data_type_name
                )

                if data_item.data_item_name != data_item_name:
                    existing_data_item =DataItem.objects.filter(
                        tenant=tenant,
                        data_format=data_convert.data_format_before,
                        data_item_name=data_item_name
                    ).first()
                    if not existing_data_item:
                        last_data_item = DataItem.objects.order_by('-id').first()
                        data_item_id = f"D000{int(last_data_item.data_item_id.split('D000')[1]) + 1}"

                        new_data_item = DataItem.objects.create(
                            tenant=tenant,
                            data_format=data_convert.data_format_before,
                            data_item_id=data_item_id,
                            data_item_name=data_item_name
                        )

                        DataItemType.objects.create(
                            data_item=new_data_item,
                            type_name=data_type_name,
                            index_value=index_value,
                            display=display_val,
                            edit_value=edit_val,
                            format_value=format_value
                        )

                        item_type.delete()

                        return JsonResponse({
                            'status': 'success',
                            'message': Mess.UPDATE.value
                        })

                    item_type.data_item=existing_data_item
                    item_type.save()

                item_type.index_value = index_value
                item_type.display = display_val
                item_type.edit_value = edit_val
                item_type.format_value = format_value
                item_type.save()

                return JsonResponse({
                    'status': 'success',
                    'message': Mess.UPDATE.value
                })

        except Exception as e:
            logger.error(f"Error in update_datatable_data: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': Mess.ERROR.value
            }, status=500)


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
                    'message': Mess.ERROR_EXIST.value
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
                'message': Mess.ERROR.value
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

            return JsonResponse({
                'status': 'success',
                'messages': Mess.DELETE.value
            })
        except Exception as e:
            logger.error(f"Delete error: {e}")
            return JsonResponse({
                'status': 'error',
                'message': Mess.ERROR.value
            }, status=500)
