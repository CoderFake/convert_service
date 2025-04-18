from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views import View
from django.db.models import Q

from configs.data_type import Mess
from configs.models import ConvertRule, ConvertDataValue, ConvertRuleCategory
from home.models import DataFormat, FileFormat

import logging
import json

logger = logging.getLogger(__name__)


class FixedDataListView(LoginRequiredMixin, View):
    def get(self, request):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return self.get_datatable_data(request)
        else:
            return self.render_page(request)

    def render_page(self, request):
        return render(request, 'web/settings/fixed-data.html')

    def get_datatable_data(self, request):
        try:
            tenant = request.user.tenant
            draw = int(request.GET.get('draw', 1))
            start = int(request.GET.get('start', 0))
            length = int(request.GET.get('length', 10))
            search_value = request.GET.get('search[value]', '')

            base_queryset = ConvertRule.objects.filter(convert_rule_category__convert_rule_category_id='CRC_FIXED')

            if search_value:
                base_queryset = base_queryset.filter(
                    Q(convert_rule_name__icontains=search_value) |
                    Q(convert_rule_id__icontains=search_value)
                )

            total_records = base_queryset.count()
            records_filtered = base_queryset.count()

            if int(length) == -1:
                paginated_items = base_queryset.order_by('id')
            else:
                paginated_items = base_queryset.order_by('id')[start:start + length]

            data = []
            for index, item in enumerate(paginated_items, start=start + 1):
                data.append({
                    'DT_RowId': f'row_{item.id}',
                    'no': index,
                    'id': item.id,
                    'convert_rule_id': item.convert_rule_id,
                    'convert_rule_name': item.convert_rule_name
                })

            response = {
                'draw': draw,
                'recordsTotal': total_records,
                'recordsFiltered': records_filtered,
                'data': data
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


class FixedDataDetailView(LoginRequiredMixin, View):
    def get(self, request, rule_id):
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request type'}, status=400)

        tenant = request.user.tenant
        try:
            fixed_category = ConvertRuleCategory.objects.filter(convert_rule_category_id='CRC_FIXED').first()
            rule = get_object_or_404(ConvertRule, id=rule_id)

            if fixed_category and rule.convert_rule_category_id != fixed_category.id:
                return JsonResponse({
                    'status': 'error',
                    'message': 'このルールは固定データ設定に対応していません。'
                }, status=400)
            fixed_data_items = ConvertDataValue.objects.filter(
                tenant=tenant,
                convert_rule=rule
            ).order_by('id')
            items = [
                {
                    'id': item.id,
                    'data_value_before': item.data_value_before,
                    'data_value_after': item.data_value_after,
                    'file_format_id': item.data_format.file_format.file_format_id if item.data_format and item.data_format.file_format else None
                }
                for item in fixed_data_items
            ]

            return JsonResponse({
                'status': 'success',
                'data': {
                    'rule_id': rule.id,
                    'rule_name': rule.convert_rule_name,
                    'rule_category': rule.convert_rule_category.convert_rule_category_name if rule.convert_rule_category else '',
                    'items': items
                }
            })

        except Exception as e:
            logger.error(f"Error fetching fixed data: {e}")
            return JsonResponse({
                'status': 'error',
                'message': Mess.ERROR.value
            }, status=500)


class FixedDataBatchSaveView(LoginRequiredMixin, View):
    def post(self, request):
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request type'}, status=400)

        tenant = request.user.tenant
        try:
            data = json.loads(request.body)
            rule_id = data.get('rule_id')
            file_format_id = data.get('file_format_id')
            items = data.get('items', [])

            if not rule_id:
                return JsonResponse({
                    'status': 'error',
                    'errors': {'rule_id': '変換ルールは必須です。'}
                }, status=400)

            if not items:
                return JsonResponse({
                    'status': 'error',
                    'errors': {'items': '少なくとも1つのアイテムが必要です。'}
                }, status=400)

            with transaction.atomic():
                fixed_category = ConvertRuleCategory.objects.filter(convert_rule_category_id='CRC_FIXED').first()
                rule = get_object_or_404(ConvertRule, id=rule_id)

                if fixed_category and rule.convert_rule_category_id != fixed_category.id:
                    return JsonResponse({
                        'status': 'error',
                        'errors': {'rule_id': 'このルールは固定データ設定に対応していません。'}
                    }, status=400)

                data_format = None

                if file_format_id:
                    file_format = get_object_or_404(FileFormat, file_format_id__contains=file_format_id)
                    data_format = DataFormat.objects.filter(
                        tenant=tenant,
                        file_format=file_format
                    ).first()
                ConvertDataValue.objects.filter(
                    tenant=tenant,
                    convert_rule=rule,
                    data_format=data_format
                ).delete()
                for item in items:
                    before_value = item.get('before')
                    after_value = item.get('after')

                    if before_value and after_value:
                        ConvertDataValue.objects.create(
                            tenant=tenant,
                            convert_rule=rule,
                            data_format=data_format,
                            data_value_before=before_value,
                            data_value_after=after_value
                        )

                return JsonResponse({
                    'status': 'success',
                    'message': Mess.CREATE.value
                })

        except Exception as e:
            logger.error(f"Error saving fixed data batch: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': Mess.ERROR.value
            }, status=500)


class FixedDataDeleteView(LoginRequiredMixin, View):
    def post(self, request, item_id=None, rule_id=None):
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request type'}, status=400)

        tenant = request.user.tenant
        try:
            if item_id:
                fixed_data = get_object_or_404(ConvertDataValue, id=item_id, tenant=tenant)
                fixed_category = ConvertRuleCategory.objects.filter(convert_rule_category_id='CRC_FIXED').first()
                if fixed_category and fixed_data.convert_rule.convert_rule_category_id != fixed_category.id:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'このルールは固定データ設定に対応していません。'
                    }, status=400)

                fixed_data.delete()
            elif rule_id:
                data = json.loads(request.body)
                file_format_id = data.get('file_format_id')
                fixed_category = ConvertRuleCategory.objects.filter(convert_rule_category_id='CRC_FIXED').first()
                rule = get_object_or_404(ConvertRule, id=rule_id)

                if fixed_category and rule.convert_rule_category_id != fixed_category.id:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'このルールは固定データ設定に対応していません。'
                    }, status=400)

                query = {
                    'tenant': tenant,
                    'convert_rule_id': rule_id
                }

                if file_format_id:
                    query['data_format__file_format__file_format_id__contains'] = file_format_id

                ConvertDataValue.objects.filter(**query).delete()
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': '無効なリクエストです。'
                }, status=400)

            return JsonResponse({
                'status': 'success',
                'message': Mess.DELETE.value
            })

        except Exception as e:
            logger.error(f"Error deleting fixed data: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': Mess.ERROR.value
            }, status=500)