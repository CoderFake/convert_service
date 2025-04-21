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


class FixedRuleCreateView(LoginRequiredMixin, View):
    def post(self, request):
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request type'}, status=400)

        tenant = request.user.tenant
        rule_name = request.POST.get('rule_name')
        rule_category = request.POST.get('rule_category')
        rule_description = request.POST.get('rule_description', '')

        errors = {}
        if not rule_name or not rule_category:
            if not rule_name:
                errors['rule_name'] = 'このフィールドは必須です。'
            if not rule_category:
                errors['rule_category'] = 'このフィールドは必須です。'

            return JsonResponse({
                'status': 'error',
                'errors': errors,
            }, status=200)

        try:
            # Get fixed rule category
            fixed_category = ConvertRuleCategory.objects.get(id=rule_category)
            if fixed_category.convert_rule_category_id != 'CRC_FIXED':
                return JsonResponse({
                    'status': 'error',
                    'errors': {'rule_category': '無効なカテゴリです。'}
                }, status=400)

            # Check if rule with similar name already exists
            existing_rule = ConvertRule.objects.filter(
                convert_rule_name=rule_name,
                convert_rule_category=fixed_category
            ).first()

            if existing_rule:
                return JsonResponse({
                    'status': 'error',
                    'errors': {'rule_name': 'この名前のルールは既に存在します。'}
                }, status=400)

            # Generate a unique rule ID
            last_rule = ConvertRule.objects.filter(
                convert_rule_category=fixed_category
            ).order_by('-id').first()

            rule_id_suffix = '001'
            if last_rule:
                # Extract number from last rule ID and increment
                if last_rule.convert_rule_id.startswith('CR_FIXED_'):
                    try:
                        last_num = int(last_rule.convert_rule_id.split('CR_FIXED_')[1])
                        rule_id_suffix = f"{last_num + 1:03d}"
                    except (ValueError, IndexError):
                        pass

            # Create the new rule
            convert_rule_id = f"CR_FIXED_{rule_id_suffix}"
            new_rule = ConvertRule.objects.create(
                convert_rule_id=convert_rule_id,
                convert_rule_name=rule_name,
                convert_rule_category=fixed_category,
                convert_rule_description=rule_description
            )

            return JsonResponse({
                'status': 'success',
                'message': Mess.CREATE.value,
                'data': {
                    'rule_id': new_rule.id,
                    'convert_rule_id': new_rule.convert_rule_id,
                    'convert_rule_name': new_rule.convert_rule_name
                }
            })

        except Exception as e:
            logger.error(f"Error creating fixed rule: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': Mess.ERROR.value
            }, status=500)


class FixedRuleUpdateView(LoginRequiredMixin, View):
    def post(self, request, rule_id):
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request type'}, status=400)

        tenant = request.user.tenant
        rule_name = request.POST.get('rule_name')
        rule_category = request.POST.get('rule_category')
        rule_description = request.POST.get('rule_description', '')

        errors = {}
        if not rule_name or not rule_category:
            if not rule_name:
                errors['rule_name'] = 'このフィールドは必須です。'
            if not rule_category:
                errors['rule_category'] = 'このフィールドは必須です。'

            return JsonResponse({
                'status': 'error',
                'errors': errors,
            }, status=200)

        try:
            # Get the rule to update
            rule = get_object_or_404(ConvertRule, id=rule_id)
            fixed_category = ConvertRuleCategory.objects.get(id=rule_category)

            if fixed_category.convert_rule_category_id != 'CRC_FIXED':
                return JsonResponse({
                    'status': 'error',
                    'errors': {'rule_category': '無効なカテゴリです。'}
                }, status=400)

            # Check for name uniqueness, excluding this rule
            existing_rule = ConvertRule.objects.filter(
                convert_rule_name=rule_name,
                convert_rule_category=fixed_category
            ).exclude(id=rule_id).first()

            if existing_rule:
                return JsonResponse({
                    'status': 'error',
                    'errors': {'rule_name': 'この名前のルールは既に存在します。'}
                }, status=400)

            # Update the rule
            rule.convert_rule_name = rule_name
            rule.convert_rule_category = fixed_category
            rule.convert_rule_description = rule_description
            rule.save()

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
        # Get all fixed rule categories to pass to template
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

            # Get only fixed category rules
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
                paginated_items = base_queryset.order_by('id')
            else:
                paginated_items = base_queryset.order_by('id')[start:start + length]

            data = []
            for index, item in enumerate(paginated_items, start=start + 1):
                data.append({
                    'DT_RowId': f'row_{item.id}',
                    'no': index,
                    'id': item.id,
                    'rule_id': item.id,  # Add this for edit button
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
            # Check if rule exists and is a fixed data rule
            fixed_category = ConvertRuleCategory.objects.filter(convert_rule_category_id='CRC_FIXED').first()
            rule = get_object_or_404(ConvertRule, id=rule_id)

            if not fixed_category or rule.convert_rule_category.id != fixed_category.id:
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
                    'rule_category_id': rule.convert_rule_category.id if rule.convert_rule_category else None,
                    'rule_description': getattr(rule, 'convert_rule_description', ''),
                    'items': items
                }
            })

        except Exception as e:
            logger.error(f"Error fetching fixed data: {e}")
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
                fixed_category = ConvertRuleCategory.objects.filter(convert_rule_category_id='CRC_FIXED').first()
                rule = get_object_or_404(ConvertRule, id=item_id)

                if not fixed_category or rule.convert_rule_category.id != fixed_category.id:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'このルールは固定データ設定に対応していません。'
                    }, status=400)

                ConvertDataValue.objects.filter(
                    tenant=tenant,
                    convert_rule=rule
                ).delete()

                rule.delete()

                return JsonResponse({
                    'status': 'success',
                    'message': Mess.DELETE.value
                })

            elif rule_id:
                fixed_category = ConvertRuleCategory.objects.filter(convert_rule_category_id='CRC_FIXED').first()
                rule = get_object_or_404(ConvertRule, id=rule_id)

                if not fixed_category or rule.convert_rule_category.id != fixed_category.id:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'このルールは固定データ設定に対応していません。'
                    }, status=400)

                ConvertDataValue.objects.filter(
                    tenant=tenant,
                    convert_rule=rule
                ).delete()

                return JsonResponse({
                    'status': 'success',
                    'message': '固定データ値が削除されました。'
                })
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': '無効なリクエストです。'
                }, status=400)

        except Exception as e:
            logger.error(f"Error deleting fixed data: {str(e)}", exc_info=True)
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

                if fixed_category and rule.convert_rule_category.id != fixed_category.id:
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

                # Delete existing items for this rule
                existing_items = ConvertDataValue.objects.filter(
                    tenant=tenant,
                    convert_rule=rule,
                )
                if data_format:
                    existing_items = existing_items.filter(data_format=data_format)

                # Keep track of IDs to delete and IDs to keep
                existing_ids = set(existing_items.values_list('id', flat=True))
                saved_ids = set()

                # Process items
                for item in items:
                    item_id = item.get('id')
                    before_value = item.get('before')
                    after_value = item.get('after')

                    if not before_value or not after_value:
                        continue

                    if item_id and int(item_id) in existing_ids:
                        # Update existing item
                        existing_item = ConvertDataValue.objects.get(id=item_id)
                        existing_item.data_value_before = before_value
                        existing_item.data_value_after = after_value
                        existing_item.save()
                        saved_ids.add(int(item_id))
                    else:
                        # Create new item
                        new_item = ConvertDataValue.objects.create(
                            tenant=tenant,
                            convert_rule=rule,
                            data_format=data_format,
                            data_value_before=before_value,
                            data_value_after=after_value
                        )
                        saved_ids.add(new_item.id)

                ids_to_delete = existing_ids - saved_ids
                if ids_to_delete:
                    ConvertDataValue.objects.filter(id__in=ids_to_delete).delete()

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