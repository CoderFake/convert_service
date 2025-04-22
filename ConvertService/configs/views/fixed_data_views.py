from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q, Subquery, OuterRef, Count
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views import View
from math import ceil

from configs.data_type import Mess
from configs.models import ConvertRule, ConvertDataValue, ConvertRuleCategory
from collections import defaultdict

import logging
import json

logger = logging.getLogger(__name__)


class FixedRuleCreateView(LoginRequiredMixin, View):
    def post(self, request):
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request type'}, status=400)

        tenant = request.user.tenant
        rule_fixed_id = request.POST.get('rule_fixed_id')
        rule_name = request.POST.get('rule_name')

        errors = {}
        if not rule_fixed_id or not rule_name:
            if not rule_fixed_id:
                errors['rule_fixed_id'] = 'このフィールドは必須です。'
            if not rule_name:
                errors['rule_name'] = 'このフィールドは必須です。'

            return JsonResponse({
                'status': 'error',
                'errors': errors,
            }, status=200)

        data = request.POST
        value_to_indices = defaultdict(list)
        fixed_values = []

        for key in data:
            if key.startswith('fixed_values[') and key.endswith('][before]'):
                row_index = key.split('[')[1].split(']')[0]
                value = data.get(key)
                value_to_indices[value].append(row_index)

                before_value = data.get(key)
                after_value = data.get(f'fixed_values[{row_index}][after]')
                fixed_values.append((row_index, before_value, after_value))

        for value, indices in value_to_indices.items():
            if len(indices) > 1:
                for row_index in indices:
                    errors[f'before-value-{row_index}'] = Mess.ERROR_EXIST.value

        if errors:
            return JsonResponse({'status': 'error', 'errors': errors}, status=200)

        existing_rule = ConvertRule.objects.filter(convert_rule_id=rule_fixed_id).first()

        if existing_rule:
            errors['rule_fixed_id'] = Mess.ERROR_EXIST.value
            return JsonResponse({
                'status': 'error',
                'errors': errors,
            })

        if fixed_values:
            for row_index, before_value, _ in fixed_values:
                existing_values = ConvertDataValue.objects.filter(
                    tenant=tenant,
                    data_value_before=before_value,
                    convert_rule_id=rule_fixed_id
                )

                if existing_values.exists():
                    errors[
                        f'before-value-{row_index}'] = Mess.ERROR_EXIST.value
                    return JsonResponse({
                        'status': 'error',
                        'errors': errors,
                    }, status=400)

        try:
            convert_rule_category = ConvertRuleCategory.objects.filter(convert_rule_category_id="CRC_FIXED").first()

            with transaction.atomic():
                new_convert_rule_fixed = ConvertRule.objects.create(
                    convert_rule_id=rule_fixed_id,
                    convert_rule_name=rule_name,
                    convert_rule_category=convert_rule_category
                )

                for _, before_value, after_value in fixed_values:
                    ConvertDataValue.objects.create(
                        tenant=tenant,
                        convert_rule=new_convert_rule_fixed,
                        data_value_before=before_value,
                        data_value_after=after_value
                    )

                return JsonResponse({
                    'status': 'success',
                    'message': Mess.CREATE.value,
                    'data': {
                        'rule_id': new_convert_rule_fixed.id
                    }
                })
        except Exception as e:
            logger.error(f"Error creating fixed rule: {str(e)}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': Mess.ERROR.value}, status=500)


class FixedRuleUpdateView(LoginRequiredMixin, View):
    def post(self, request, rule_id):
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request type'}, status=400)

        tenant = request.user.tenant
        rule_fixed_id = request.POST.get('rule_fixed_id')
        rule_name = request.POST.get('rule_name')

        errors = {}
        if not rule_fixed_id or not rule_name:
            if not rule_fixed_id:
                errors['rule_fixed_id'] = Mess.ERROR_REQUIRED.value
            if not rule_name:
                errors['rule_name'] = Mess.ERROR_REQUIRED.value

            return JsonResponse({
                'status': 'error',
                'errors': errors,
            }, status=200)

        data = request.POST
        value_to_indices = defaultdict(list)
        fixed_values = []
        for key in data:
            if key.startswith('fixed_values[') and key.endswith('][before]'):
                row_index = key.split('[')[1].split(']')[0]
                before_value = data.get(key)
                after_value = data.get(f'fixed_values[{row_index}][after]')
                fixed_values.append((row_index, before_value, after_value))

                value = before_value
                value_to_indices[value].append(row_index)


        for value, indices in value_to_indices.items():
            if len(indices) > 1:
                for row_index in indices:
                    errors[f'before-value-{row_index}'] = Mess.ERROR_EXIST.value

        if errors:
            return JsonResponse({'status': 'error', 'errors': errors}, status=200)

        try:
            rule = get_object_or_404(ConvertRule, id=rule_id)
            existing_rule_id = ConvertRule.objects.filter(
                convert_rule_id=rule_fixed_id
            ).exclude(id=rule_id).first()

            if existing_rule_id:
                return JsonResponse({
                    'status': 'error',
                    'errors': {'rule_fixed_id': Mess.ERROR_EXIST.value}
                }, status=400)

            with transaction.atomic():
                rule.convert_rule_id = rule_fixed_id
                rule.convert_rule_name = rule_name
                rule.save()

                if fixed_values:
                    for index, before_value, after_value in fixed_values:
                        existing = ConvertDataValue.objects.filter(
                            tenant=tenant,
                            convert_rule=rule,
                            data_value_before=before_value
                        ).first()

                        if existing:
                            transaction.set_rollback(True)

                            errors[f'before-value-{index}'] = Mess.ERROR_EXIST.value
                            return JsonResponse({
                                'status': 'error',
                                'errors': errors
                            }, status=200)

                        ConvertDataValue.objects.create(
                            tenant=tenant,
                            convert_rule=rule,
                            data_value_before=before_value,
                            data_value_after=after_value
                        )


            return JsonResponse({
                'status': 'success',
                'message': Mess.UPDATE.value,
                'data': {
                    'rule_id': rule.id,
                    'convert_rule_id': rule.convert_rule_id,
                    'convert_rule_name': rule.convert_rule_name
                }
            })

        except Exception as e:
            logger.error(f"Error updating fixed rule: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': Mess.ERROR.value
            }, status=500)


class FixedDataListView(LoginRequiredMixin, View):
    def get(self, request):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return self.get_datatable_data(request)
        else:
            return self.render_page(request)

    def render_page(self, request):
        fixed_categories = ConvertRuleCategory.objects.filter(convert_rule_category_id='CRC_FIXED')
        context = {
            'rule_categories': fixed_categories
        }
        return render(request, 'web/settings/fixed-data.html', context)

    def get_datatable_data(self, request):
        try:
            draw = int(request.GET.get('draw', 1))
            start = int(request.GET.get('start', 0))
            length = int(request.GET.get('length', 10))
            search_value = request.GET.get('search[value]', '')

            fixed_category = ConvertRuleCategory.objects.filter(convert_rule_category_id='CRC_FIXED').first()

            if not fixed_category:
                return JsonResponse({
                    'draw': draw,
                    'recordsTotal': 0,
                    'recordsFiltered': 0,
                    'data': []
                })

            base_queryset = ConvertRule.objects.filter(convert_rule_category=fixed_category)

            if search_value:
                base_queryset = base_queryset.filter(
                    Q(convert_rule_name__icontains=search_value) |
                    Q(convert_rule_id__icontains=search_value)
                ).distinct()

            total_records = base_queryset.count()
            records_filtered = base_queryset.count()

            if int(length) == -1:
                paginated_items = base_queryset.order_by('-updated_at')
            else:
                paginated_items = base_queryset.order_by('-updated_at')[start:start + length]

            data = []
            for index, item in enumerate(paginated_items, start=start + 1):
                data.append({
                    'DT_RowId': f'row_{item.id}',
                    'no': index,
                    'id': item.id,
                    'rule_id': item.id,
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
            rule = get_object_or_404(ConvertRule, id=rule_id)
            fixed_data_items = ConvertDataValue.objects.filter(
                tenant=tenant,
                convert_rule=rule
            ).values('data_value_before', 'data_value_after').distinct()[:10]

            items = [
                {
                    'id': idx,
                    'data_value_before': item['data_value_before'],
                    'data_value_after': item['data_value_after'],
                    'file_format_id': None
                }
                for idx, item in enumerate(fixed_data_items, 1)
            ]

            return JsonResponse({
                'status': 'success',
                'data': {
                    'rule_id': rule.id,
                    'rule_fixed_id': rule.convert_rule_id,
                    'rule_name': rule.convert_rule_name,
                    'rule_category': rule.convert_rule_category.convert_rule_category_name if rule.convert_rule_category else '',
                    'rule_category_id': rule.convert_rule_category.id if rule.convert_rule_category else None,
                    'items': items
                }
            })

        except Exception as e:
            logger.error(f"Error fetching fixed data: {e}")
            return JsonResponse({
                'status': 'error',
                'message': Mess.ERROR.value
            }, status=500)


class FixedDataValuesView(LoginRequiredMixin, View):
    def get(self, request, rule_id):
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request type'}, status=400)

        tenant = request.user.tenant
        try:
            rule = ConvertRule.objects.filter(id=rule_id).first()

            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 10))
            search = request.GET.get('search', '').strip()

            query = ConvertDataValue.objects.filter(
                tenant=tenant,
                convert_rule=rule
            ).values('data_value_before', 'data_value_after').distinct()

            if search:
                query = query.filter(
                    Q(data_value_before__icontains=search) |
                    Q(data_value_after__icontains=search)
                )

            total_items = query.count()
            total_pages = ceil(total_items / page_size)

            if page < 1:
                page = 1
            elif page > total_pages and total_pages > 0:
                page = total_pages

            start_index = (page - 1) * page_size + 1
            end_index = min(start_index + page_size - 1, total_items)

            items = query.order_by('data_value_before')[(page - 1) * page_size:page * page_size]

            formatted_items = []
            for idx, item in enumerate(items, start=1):
                sample_id = ConvertDataValue.objects.filter(
                    tenant=tenant,
                    convert_rule=rule,
                    data_value_before=item['data_value_before'],
                    data_value_after=item['data_value_after']
                ).values_list('id', flat=True).first() or idx

                formatted_items.append({
                    'id': sample_id,
                    'before': item['data_value_before'],
                    'after': item['data_value_after']
                })

            return JsonResponse({
                'status': 'success',
                'items': formatted_items,
                'pagination': {
                    'current_page': page,
                    'page_size': page_size,
                    'total_pages': total_pages,
                    'total_items': total_items,
                    'start_index': start_index,
                    'end_index': end_index
                }
            })

        except Exception as e:
            logger.error(f"Error fetching fixed data values: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': Mess.ERROR.value
            }, status=500)


class FixedDataDeleteValueView(LoginRequiredMixin, View):
    def post(self, request):
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request type'}, status=400)

        tenant = request.user.tenant
        try:
            data = json.loads(request.body)
            rule_id = data.get('rule_id')
            before_value = data.get('before_value')
            after_value = data.get('after_value')

            if not rule_id:
                return JsonResponse({
                    'status': 'error',
                    'message': Mess.ERROR.value
                }, status=400)

            filter_params = {
                'tenant': tenant,
                'convert_rule_id': rule_id,
                'data_value_before': before_value,
                'data_value_after': after_value
            }

            current_convert_value = ConvertDataValue.objects.filter(**filter_params).first()

            if not current_convert_value:
                return JsonResponse({
                    'status': 'error',
                    'message': Mess.NOTFOUND.value
                })
            current_convert_value.delete()

            return JsonResponse({
                'status': 'success',
                'message': Mess.DELETE.value
            })

        except Exception as e:
            logger.error(f"Error deleting fixed data value: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': Mess.ERROR.value
            }, status=500)


class FixedRuleDeleteView(LoginRequiredMixin, View):
    def post(self, request, item_id=None):
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request type'}, status=400)

        tenant = request.user.tenant
        try:
            if item_id:
                rule = get_object_or_404(ConvertRule, id=item_id)

                ConvertDataValue.objects.filter(
                    tenant=tenant,
                    convert_rule=rule
                ).delete()

                rule.delete()

                return JsonResponse({
                    'status': 'success',
                    'message': Mess.DELETE.value
                })

            else:
                return JsonResponse({
                    'status': 'error',
                    'message': Mess.ERROR.value
                }, status=400)

        except Exception as e:
            logger.error(f"Error deleting fixed data: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': Mess.ERROR.value
            }, status=500)


class FixedDataUpdateValueView(LoginRequiredMixin, View):
    def post(self, request):
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request type'}, status=400)

        tenant = request.user.tenant
        try:
            data = json.loads(request.body)
            item_id = data.get('item_id')
            rule_id = data.get('rule_id')
            before_value = data.get('before_value', '')
            after_value = data.get('after_value', '')

            if not rule_id:
                return JsonResponse({
                    'status': 'error',
                    'message': Mess.NOTFOUND.value
                }, status=200)

            current_item = ConvertDataValue.objects.filter(id=item_id).first()
            if not current_item:
                return JsonResponse({
                    'status': 'error',
                    'message': Mess.NOTFOUND.value
                }, status=200)

            old_before_value = current_item.data_value_before

            if before_value != old_before_value:
                existing_values = ConvertDataValue.objects.filter(
                    tenant=tenant,
                    convert_rule_id=rule_id,
                    data_value_before=before_value
                ).exclude(id=item_id)

                if existing_values.exists():
                    return JsonResponse({
                        'status': 'error',
                        'message': Mess.ERROR_EXIST.value
                    }, status=400)

            if before_value != old_before_value:
                other_rule_values = ConvertDataValue.objects.filter(
                    tenant=tenant,
                    data_value_before=before_value
                ).exclude(convert_rule_id=rule_id)

                if other_rule_values.exists():
                    return JsonResponse({
                        'status': 'error',
                        'message': Mess.ERROR_EXIST.value,
                    }, status=400)

            with transaction.atomic():
                affected_items = ConvertDataValue.objects.filter(
                    tenant=tenant,
                    convert_rule_id=rule_id,
                    data_value_before=old_before_value,
                    data_value_after=current_item.data_value_after
                )

                update_count = affected_items.update(
                    data_value_before=before_value,
                    data_value_after=after_value
                )

                return JsonResponse({
                    'status': 'success',
                    'message': Mess.UPDATE.value,
                    'update_count': update_count
                })

        except Exception as e:
            logger.error(f"Error updating fixed data value: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': Mess.ERROR.value
            }, status=500)