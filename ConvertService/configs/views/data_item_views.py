from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View

from home.models import DataItem, FileFormat, DataFormat, DataItemType

import logging

logger = logging.getLogger(__name__)


class DataItemListView(LoginRequiredMixin, View):
    def get(self, request):
        tenant = request.user.tenant
        data_items = DataItem.objects.filter(tenant=tenant).select_related('data_format')
        file_formats = FileFormat.objects.all()

        excel_items = data_items.filter(data_format__file_format__file_format_id__icontains='EXCEL')
        csv_items = data_items.filter(data_format__file_format__file_format_id__icontains='CSV')

        context = {
            'excel_items': excel_items,
            'csv_items': csv_items,
            'file_formats': file_formats
        }

        return render(request, 'web/settings/data-item.html', context)


class DataItemCreateView(LoginRequiredMixin, View):
    def get(self, request):
        tenant = request.user.tenant
        data_formats = DataFormat.objects.filter(tenant=tenant)

        context = {
            'data_formats': data_formats,
            'data_types': DataItemType.FormatValue.choices
        }

        return render(request, 'web/settings/dataitem-create.html', context)

    def post(self, request):
        try:
            with transaction.atomic():
                tenant = request.user.tenant
                data_item_id = request.POST.get('data_item_id')
                data_item_name = request.POST.get('data_item_name')
                data_format_id = request.POST.get('data_format_id')
                if DataItem.objects.filter(data_item_id=data_item_id).exists():
                    return JsonResponse({'status': 'error', 'message': 'Mã trường dữ liệu đã tồn tại'})
                data_format = get_object_or_404(DataFormat, id=data_format_id, tenant=tenant)
                data_item = DataItem.objects.create(
                    tenant=tenant,
                    data_format=data_format,
                    data_item_id=data_item_id,
                    data_item_name=data_item_name
                )
                DataItemType.objects.create(
                    data_item=data_item,
                    type_name=DataItemType.TypeName.BEFORE,
                    index_value=0,
                    display=False,
                    edit_value=False,
                    format_value='string'
                )

                DataItemType.objects.create(
                    data_item=data_item,
                    type_name=DataItemType.TypeName.FORMAT,
                    index_value=0,
                    display=True,
                    edit_value=False,
                    format_value='string'
                )

                DataItemType.objects.create(
                    data_item=data_item,
                    type_name=DataItemType.TypeName.AFTER,
                    index_value=0,
                    display=True,
                    edit_value=False,
                    format_value='string'
                )

                messages.success(request, f'Đã tạo trường dữ liệu "{data_item_name}" thành công')
                return redirect('dataitem_list')

        except Exception as e:
            logger.error(f"Lỗi khi tạo DataItem: {e}")
            messages.error(request, f'Lỗi: {str(e)}')
            return redirect('dataitem_create')


class DataItemEditView(LoginRequiredMixin, View):
    def get(self, request, item_id):
        tenant = request.user.tenant
        data_item = get_object_or_404(DataItem, id=item_id, tenant=tenant)
        data_formats = DataFormat.objects.filter(tenant=tenant)
        item_types = DataItemType.objects.filter(data_item=data_item)

        context = {
            'data_item': data_item,
            'data_formats': data_formats,
            'data_types': DataItemType.FormatValue.choices,
            'item_types': {t.type_name: t for t in item_types}
        }

        return render(request, 'web/settings/edit.html', context)

    def post(self, request, item_id):
        try:
            with transaction.atomic():
                tenant = request.user.tenant
                data_item = get_object_or_404(DataItem, id=item_id, tenant=tenant)
                data_item.data_item_name = request.POST.get('data_item_name')
                data_format_id = request.POST.get('data_format_id')
                data_item.data_format = get_object_or_404(DataFormat, id=data_format_id)
                data_item.save()
                for type_name in [DataItemType.TypeName.BEFORE, DataItemType.TypeName.FORMAT,
                                  DataItemType.TypeName.AFTER]:
                    item_type, created = DataItemType.objects.get_or_create(
                        data_item=data_item,
                        type_name=type_name
                    )
                    display_key = f'display_{type_name}'
                    edit_key = f'edit_{type_name}'
                    format_key = f'format_{type_name}'
                    index_key = f'index_{type_name}'

                    item_type.display = request.POST.get(display_key) == 'on'
                    item_type.edit_value = request.POST.get(edit_key) == 'on'
                    item_type.format_value = request.POST.get(format_key, 'string')
                    item_type.index_value = int(request.POST.get(index_key, '0'))
                    item_type.save()

                messages.success(request, f'Đã cập nhật trường dữ liệu "{data_item.data_item_name}" thành công')
                return redirect('dataitem_list')

        except Exception as e:
            logger.error(f"Lỗi khi cập nhật DataItem: {e}")
            messages.error(request, f'Lỗi: {str(e)}')
            return redirect('dataitem_edit', item_id=item_id)


class DataItemDeleteView(LoginRequiredMixin, View):
    def post(self, request, item_id):
        try:
            tenant = request.user.tenant
            data_item = get_object_or_404(DataItem, id=item_id, tenant=tenant)
            DataItemType.objects.filter(data_item=data_item).delete()
            data_item_name = data_item.data_item_name
            data_item.delete()

            messages.success(request, f'Đã xóa trường dữ liệu "{data_item_name}" thành công')
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
