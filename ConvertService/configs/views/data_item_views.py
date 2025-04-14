import json
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q, F
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views import View
from django.core.paginator import Paginator

from home.models import DataItem, FileFormat, DataFormat, DataItemType

import logging

logger = logging.getLogger(__name__)


class DataItemListView(LoginRequiredMixin, View):
    def get(self, request):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return self.get_datatable_data(request)
        else:
            return self.render_page(request)

    def render_page(self, request):
        tenant = request.user.tenant
        file_formats = FileFormat.objects.all()
        data_type_choices = DataItemType.TypeName.choices
        data_formats_list = DataFormat.objects.filter(tenant=tenant).select_related('file_format')
        data_item_type_format_choices = [
            ('input', '変換前のデータ'),
            ('format', '画面のデータ'),
            ('output', '健診システム取り込みデータ'),
            ('input', '予約代行業者取り込みデータ'),
        ]


        context = {
            'file_formats': file_formats,
            'data_type_choices': data_type_choices,
            'data_type_choices_json': json.dumps(dict(data_type_choices)),
            'data_formats': data_formats_list,
            'data_item_type_format_choices': data_item_type_format_choices
        }
        return render(request, 'web/settings/data-item.html', context)

    def get_datatable_data(self, request):
        tenant = request.user.tenant
        draw = int(request.GET.get('draw', 1))
        start = int(request.GET.get('start', 0))
        length = int(request.GET.get('length', 10))
        search_value = request.GET.get('search[value]', '')
        file_format_id = request.GET.get('file_format_id', '')
        data_type_name = request.GET.get('data_type_name', DataItemType.TypeName.BEFORE)

        queryset = DataItem.objects.filter(tenant=tenant).select_related(
            'data_format', 'data_format__file_format'
        ).prefetch_related('data_item_types')

        if file_format_id:
            queryset = queryset.filter(data_format__file_format__id=file_format_id)

        queryset = queryset.annotate(
            target_type_display=F(f'data_item_types__display'),
            target_type_edit_value=F(f'data_item_types__edit_value'),
            target_type_index_value=F(f'data_item_types__index_value'),
            target_type_format_value=F(f'data_item_types__format_value')
        ).filter(data_item_types__type_name=data_type_name).distinct()

        if search_value:
            queryset = queryset.filter(
                Q(data_item_id__icontains=search_value) |
                Q(data_item_name__icontains=search_value)
            )

        total_records = DataItem.objects.filter(tenant=tenant).count()
        records_filtered = queryset.count()

        order_column_index = int(request.GET.get('order[0][column]', 0))
        order_dir = request.GET.get('order[0][dir]', 'asc')
        order_columns = ['data_item_id', 'data_item_name', None, 'target_type_display', 'target_type_edit_value', 'target_type_index_value'] # Map index to field name

        if order_column_index < len(order_columns) and order_columns[order_column_index]:
            order_field = order_columns[order_column_index]
            if order_dir == 'desc':
                order_field = f'-{order_field}'
            queryset = queryset.order_by(order_field)
        else:
             queryset = queryset.order_by('data_item_id')

        paginator = Paginator(queryset, length)
        page_number = (start // length) + 1
        page_obj = paginator.get_page(page_number)

        data = []
        for item in page_obj:
            try:
                item_type = item.data_item_types.get(type_name=data_type_name)
                display = item_type.display
                edit_value = item_type.edit_value
                index_value = item_type.index_value
            except DataItemType.DoesNotExist:
                display = False
                edit_value = False
                index_value = 0

            data.append({
                'id': item.id,
                'data_item_id': item.data_item_id,
                'data_item_name': item.data_item_name,
                'file_format_name': item.data_format.file_format.file_format_name if item.data_format and item.data_format.file_format else 'N/A',
                'display': display,
                'edit_value': edit_value,
                'index_value': index_value,
            })

        response = {
            'draw': draw,
            'recordsTotal': total_records,
            'recordsFiltered': records_filtered,
            'data': data,
        }
        return JsonResponse(response)


class DataItemCreateView(LoginRequiredMixin, View):
    def post(self, request):
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request type'}, status=400)

        tenant = request.user.tenant
        data_item_id = request.POST.get('data_item_id')
        data_item_name = request.POST.get('data_item_name')
        data_format_id = request.POST.get('data_format_id')

        errors = {}
        if not data_item_id: errors['data_item_id'] = ['This field is required.']
        if not data_item_name: errors['data_item_name'] = ['This field is required.']
        if not data_format_id: errors['data_format_id'] = ['This field is required.']
        if DataItem.objects.filter(data_item_id=data_item_id, tenant=tenant).exists():
            errors.setdefault('data_item_id', []).append('Data Item ID already exists.')

        if errors:
            return JsonResponse({'status': 'error', 'errors': errors}, status=400)

        try:
            with transaction.atomic():
                data_format = get_object_or_404(DataFormat, id=data_format_id, tenant=tenant)
                data_item = DataItem.objects.create(
                    tenant=tenant,
                    data_format=data_format,
                    data_item_id=data_item_id,
                    data_item_name=data_item_name
                )
                for type_name in DataItemType.TypeName.values:
                     DataItemType.objects.create(
                         data_item=data_item,
                         type_name=type_name,
                         index_value=0,
                         display=(type_name == DataItemType.TypeName.FORMAT or type_name == DataItemType.TypeName.AFTER),
                         edit_value=False,
                         format_value='string'
                     )

                return JsonResponse({'status': 'success', 'message': f'Data Item "{data_item_name}" created successfully.'})

        except DataFormat.DoesNotExist:
             return JsonResponse({'status': 'error', 'errors': {'data_format_id': ['Invalid Data Format selected.']}}, status=400)
        except Exception as e:
            logger.error(f"Error creating DataItem via AJAX: {e}")
            return JsonResponse({'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'}, status=500)


class DataItemEditView(LoginRequiredMixin, View):
    def post(self, request, item_id):
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request type'}, status=400)

        tenant = request.user.tenant
        try:
            with transaction.atomic():
                data_item = get_object_or_404(DataItem, id=item_id, tenant=tenant)

                data_item.data_item_name = request.POST.get('data_item_name')
                data_format_id = request.POST.get('data_format_id')

                errors = {}
                if not data_item.data_item_name: errors['data_item_name'] = ['This field is required.']
                if not data_format_id: errors['data_format_id'] = ['This field is required.']

                if errors:
                    return JsonResponse({'status': 'error', 'errors': errors}, status=400)

                data_item.data_format = get_object_or_404(DataFormat, id=data_format_id, tenant=tenant)
                data_item.save()

                type_errors = {}
                for type_name_val in DataItemType.TypeName.values:
                    item_type, created = DataItemType.objects.get_or_create(
                        data_item=data_item,
                        type_name=type_name_val,
                        defaults={'index_value': 0, 'display': False, 'edit_value': False, 'format_value': 'string'}
                    )

                    display_key = f'display_{type_name_val}'
                    edit_key = f'edit_{type_name_val}'
                    format_key = f'format_{type_name_val}'
                    index_key = f'index_{type_name_val}'

                    item_type.display = request.POST.get(display_key) == 'on'
                    item_type.edit_value = request.POST.get(edit_key) == 'on'
                    item_type.format_value = request.POST.get(format_key, 'string')
                    try:
                        item_type.index_value = int(request.POST.get(index_key, '0'))
                    except (ValueError, TypeError):
                         type_errors.setdefault(index_key, []).append('Index must be a valid number.')
                         item_type.index_value = 0

                    if item_type.format_value not in dict(DataItemType.FormatValue.choices):
                         type_errors.setdefault(format_key, []).append('Invalid format value selected.')

                    item_type.save()

                if type_errors:
                     return JsonResponse({'status': 'error', 'errors': type_errors}, status=400)


                return JsonResponse({'status': 'success', 'message': f'Data Item "{data_item.data_item_name}" updated successfully.'})

        except DataItem.DoesNotExist:
             return JsonResponse({'status': 'error', 'message': 'Data Item not found.'}, status=404)
        except DataFormat.DoesNotExist:
             return JsonResponse({'status': 'error', 'errors': {'data_format_id': ['Invalid Data Format selected.']}}, status=400)
        except Exception as e:
            logger.error(f"Error updating DataItem {item_id} via AJAX: {e}")
            return JsonResponse({'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'}, status=500)


class DataItemDetailView(LoginRequiredMixin, View):
    def get(self, request, item_id):
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request type'}, status=400)

        tenant = request.user.tenant
        try:
            data_item = get_object_or_404(DataItem, id=item_id, tenant=tenant)
            item_types = DataItemType.objects.filter(data_item=data_item)

            data_item_data = {
                'id': data_item.id,
                'data_item_id': data_item.data_item_id,
                'data_item_name': data_item.data_item_name,
                'data_format_id': data_item.data_format_id,
            }
            item_types_data = {
                t.type_name: {
                    'display': t.display,
                    'edit_value': t.edit_value,
                    'format_value': t.format_value,
                    'index_value': t.index_value,
                } for t in item_types
            }

            for type_val in DataItemType.TypeName.values:
                if type_val not in item_types_data:
                    item_types_data[type_val] = { # Default values
                         'display': False, 'edit_value': False, 'format_value': 'string', 'index_value': 0
                    }


            return JsonResponse({
                'status': 'success',
                'data_item': data_item_data,
                'item_types': item_types_data
            })

        except DataItem.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Data Item not found.'}, status=404)
        except Exception as e:
            logger.error(f"Error fetching DataItem detail {item_id}: {e}")
            return JsonResponse({'status': 'error', 'message': 'An error occurred fetching details.'}, status=500)


class DataItemDeleteView(LoginRequiredMixin, View):
    def post(self, request, item_id):
        try:
            tenant = request.user.tenant
            tenant = request.user.tenant
            data_item = get_object_or_404(DataItem, id=item_id, tenant=tenant)
            data_item_name = data_item.data_item_name

            with transaction.atomic():
                DataItemType.objects.filter(data_item=data_item).delete()
                data_item.delete()

            return JsonResponse({'status': 'success'})

        except Exception as e:
            logger.error(f"Lỗi khi xóa DataItem: {e}")
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
