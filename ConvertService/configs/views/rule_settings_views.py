from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.db.models import Q

from configs.data_type import Mess
from configs.models import ConvertRule, ConvertRuleCategory
from home.models import DetailedInfo, DataItemType, DataItem, DataConversionInfo
import logging
logger = logging.getLogger(__name__)


class RuleSettingsView(LoginRequiredMixin, View):
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
            ('input-display', '変換前のデータ ⇒ 画面のデータ'),
            ('display-system_output', '画面のデータ ⇒ 健診システム取り込みデータ'),
            ('display-agency_output', '画面のデータ ⇒ 予約代行業者取り込みデータ'),
        ]

        rule_categories = ConvertRuleCategory.objects.all()
        dynamic_rules = ConvertRule.objects.exclude(convert_rule_category__convert_rule_category_id="CRC_FIXED")
        fixed_rules = ConvertRule.objects.filter(convert_rule_category__convert_rule_category_id="CRC_FIXED")

        context = {
            'file_formats': file_formats,
            'data_item_type_choices': data_item_type_choices,
            'rule_categories': rule_categories,
            'dynamic_rules': dynamic_rules,
            'fixed_rules': fixed_rules,
        }
        return render(request, 'web/settings/rule_settings.html', context)

    def get_datatable_data(self, request):
        try:
            tenant = request.user.tenant
            draw = int(request.GET.get('draw', 1))
            start = int(request.GET.get('start', 0))
            length = int(request.GET.get('length', 10))
            search_value = request.GET.get('search[value]', '')
            file_format_id = request.GET.get('file_format_id', '')
            from_to_type = request.GET.get('from_to_type', 'input-format')

            data_convert = DataConversionInfo.objects.filter(
                tenant=tenant,
                data_format_before__file_format__file_format_id__contains=file_format_id,
            ).first()

            from_type = from_to_type.split('-')[0]
            to_type = from_to_type.split('-')[1]

            if not data_convert:
                return JsonResponse({
                    'draw': draw,
                    'recordsTotal': 0,
                    'recordsFiltered': 0,
                    'data': [],
                    'message': 'データ変換情報が見つかりません'
                })

            base_queryset = DetailedInfo.objects.filter(
                tenant=tenant,
                data_convert=data_convert,
                data_item_type_before__type_name=from_type,
                data_item_type_after__type_name=to_type
            ).select_related(
                'data_item_type_before__data_item',
                'data_item_type_after__data_item',
                'convert_rule',
                'convert_rule__convert_rule_category'
            )

            if file_format_id:
                base_queryset = base_queryset.filter(
                    data_item_type_before__data_item__data_format__file_format__file_format_id__contains=file_format_id
                )

            if search_value:
                base_queryset = base_queryset.filter(
                    Q(data_item_type_before__data_item__data_item_name__icontains=search_value) |
                    Q(data_item_type_after__data_item__data_item_name__icontains=search_value) |
                    Q(convert_rule__convert_rule_name__icontains=search_value)
                ).distinct()

            total_records = DetailedInfo.objects.filter(tenant=tenant).count()
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
                    'from_item': item.data_item_type_before.data_item.data_item_name,
                    'to_item': item.data_item_type_after.data_item.data_item_name,
                    'rule_id': item.convert_rule.id,
                    'rule_name': item.convert_rule.convert_rule_name,
                    'rule_category': item.convert_rule.convert_rule_category.convert_rule_category_name
                })

            response = {
                'draw': draw,
                'recordsTotal': total_records,
                'recordsFiltered': records_filtered,
                'data': data,
                'file_format_id': file_format_id,
                'from_to_type': from_to_type
            }
            return JsonResponse(response)

        except Exception as e:
            logger.error(e)
            return JsonResponse({
                'draw': int(request.GET.get('draw', 1)),
                'recordsTotal': 0,
                'recordsFiltered': 0,
                'data': [],
                'error': Mess.NOTFOUND.value
            })


class RuleDetailView(LoginRequiredMixin, View):
    def get(self, request, rule_id, file_format_id, from_to_type):
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request type'}, status=400)

        tenant = request.user.tenant
        try:
            from_type = from_to_type.split('-')[0]
            to_type = from_to_type.split('-')[1]

            rule = DetailedInfo.objects.filter(
                id=rule_id,
                tenant=tenant,
                data_item_type_before__data_item__data_format__file_format__file_format_id__contains=file_format_id,
                data_item_type_before__type_name=from_type,
                data_item_type_after__type_name=to_type
            ).select_related(
                'data_item_type_before__data_item',
                'data_item_type_after__data_item',
                'convert_rule'
            ).first()

            if not rule:
                return JsonResponse({
                    'status': 'error',
                    'message': Mess.ERROR.NOTFOUND.value
                }, status=404)

            from_items = DataItem.objects.filter(
                tenant=tenant,
                data_format__file_format__file_format_id__contains=file_format_id,
                data_item_types__type_name=from_type
            ).values('id', 'data_item_name').order_by('data_item_types__index_value')

            to_items = DataItem.objects.filter(
                tenant=tenant,
                data_format__file_format__file_format_id__contains=file_format_id,
                data_item_types__type_name=to_type
            ).values('id', 'data_item_name').order_by('data_item_types__index_value')

            rule_data = {
                'id': rule.id,
                'from_item_id': rule.data_item_type_before.data_item.id,
                'from_item_name': rule.data_item_type_before.data_item.data_item_name,
                'to_item_id': rule.data_item_type_after.data_item.id,
                'to_item_name': rule.data_item_type_after.data_item.data_item_name,
                'rule_id': rule.convert_rule.id,
                'rule_name': rule.convert_rule.convert_rule_name,
                'from_items': list(from_items),
                'to_items': list(to_items)
            }

            return JsonResponse({
                'status': 'success',
                'data': rule_data,
            })

        except Exception as e:
            logger.error(e)
            return JsonResponse({
                'status': 'error',
                'message': Mess.ERROR.value
            }, status=500)


class GetItemsView(LoginRequiredMixin, View):
    def get(self, request):
        try:
            tenant = request.user.tenant
            file_format_id = request.GET.get('file_format_id', '')
            type_name = request.GET.get('type_name', 'input')

            items = DataItem.objects.filter(
                tenant=tenant,
                data_format__file_format__file_format_id__contains=file_format_id,
                data_item_types__type_name=type_name
            ).values('id', 'data_item_name').order_by('data_item_types__index_value')

            return JsonResponse({
                'status': 'success',
                'items': list(items)
            })

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': Mess.ERROR.value
            }, status=500)


class RuleCreateView(LoginRequiredMixin, View):
    def post(self, request):
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request type'}, status=400)

        tenant = request.user.tenant
        from_item_id = request.POST.get('from_item_id')
        to_item_id = request.POST.get('to_item_id')
        rule_id = request.POST.get('rule_id')
        file_format_id = request.POST.get('file_format_id')
        from_to_type = request.POST.get('from_to_type')

        from_type = from_to_type.split('-')[0]
        to_type = from_to_type.split('-')[1]

        errors = {}
        if not from_item_id or not to_item_id or not rule_id:
            if not from_item_id:
                errors['from_item_id'] = Mess.ERROR_REQUIRED.value
            if not to_item_id:
                errors['to_item_id'] = Mess.ERROR_REQUIRED.value
            if not rule_id:
                errors['rule_id'] = Mess.ERROR_REQUIRED.value

            return JsonResponse({
                'status': 'error',
                'errors': errors,
            }, status=200)

        try:
            with transaction.atomic():
                from_item = get_object_or_404(DataItem, id=from_item_id, tenant=tenant)
                to_item = get_object_or_404(DataItem, id=to_item_id, tenant=tenant)
                rule = get_object_or_404(ConvertRule, id=rule_id)

                from_type_obj = DataItemType.objects.filter(
                    data_item=from_item,
                    type_name=from_type
                ).first()

                to_type_obj = DataItemType.objects.filter(
                    data_item=to_item,
                    type_name=to_type
                ).first()

                if not from_type_obj or not to_type_obj:
                    return JsonResponse({
                        'status': 'error',
                        'message': Mess.ERROR.value
                    }, status=500)

                data_convert = DataConversionInfo.objects.filter(
                    tenant=tenant,
                    data_format_before__file_format__file_format_id__contains=file_format_id,
                ).first()

                existing = DetailedInfo.objects.filter(
                    tenant=tenant,
                    data_convert=data_convert,
                    data_item_type_before=from_type_obj,
                    data_item_type_after=to_type_obj
                ).first()

                if existing:
                    errors['from_item_id'] = Mess.ERROR_EXIST.value
                    errors['to_item_id'] = Mess.ERROR_EXIST.value
                    return JsonResponse({
                        'status': 'error',
                        'errors': errors,
                    })
                else:
                    DetailedInfo.objects.create(
                        tenant=tenant,
                        data_convert=data_convert,
                        data_item_type_before=from_type_obj,
                        data_item_type_after=to_type_obj,
                        convert_rule=rule
                    )
                    return JsonResponse({
                        'status': 'success',
                        'message': Mess.CREATE.value
                    })

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': Mess.ERROR.value
            }, status=500)


class RuleEditView(LoginRequiredMixin, View):
    def post(self, request, rule_id):
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request type'}, status=400)

        tenant = request.user.tenant
        from_item_id = request.POST.get('from_item_id')
        to_item_id = request.POST.get('to_item_id')
        rule_id_new = request.POST.get('rule_id')
        from_to_type = request.POST.get('from_to_type')

        from_type = from_to_type.split('-')[0]
        to_type = from_to_type.split('-')[1]

        errors = {}
        if not from_item_id or not to_item_id or not rule_id_new:
            if not from_item_id:
                errors['from_item_id'] = Mess.ERROR_REQUIRED.value
            if not to_item_id:
                errors['to_item_id'] = Mess.ERROR_REQUIRED.value
            if not rule_id_new:
                errors['rule_id'] = Mess.ERROR_REQUIRED.value

            return JsonResponse({
                'status': 'error',
                'errors': errors,
            }, status=200)

        try:
            with transaction.atomic():
                detailed_info = get_object_or_404(DetailedInfo, id=rule_id, tenant=tenant)

                from_item = get_object_or_404(DataItem, id=from_item_id, tenant=tenant)
                to_item = get_object_or_404(DataItem, id=to_item_id, tenant=tenant)
                rule = get_object_or_404(ConvertRule, id=rule_id_new)

                from_type_obj = DataItemType.objects.filter(
                    data_item=from_item,
                    type_name=from_type
                ).first()

                to_type_obj = DataItemType.objects.filter(
                    data_item=to_item,
                    type_name=to_type
                ).first()

                if not from_type_obj or not to_type_obj:
                    return JsonResponse({
                        'status': 'error',
                        'message': Mess.ERROR_EXIST.value
                    }, status=404)


                existing_after = DetailedInfo.objects.filter(
                    tenant=tenant,
                    data_convert=detailed_info.data_convert,
                    data_item_type_after=to_type_obj
                ).exclude(id=rule_id).first()

                if existing_after:
                    errors['to_item_id'] = Mess.ERROR_EXIST.value
                    return JsonResponse({
                        'status': 'error',
                        'errors': errors,
                    })

                existing_pair = DetailedInfo.objects.filter(
                    tenant=tenant,
                    data_convert=detailed_info.data_convert,
                    data_item_type_before=from_type_obj,
                    data_item_type_after=to_type_obj
                ).exclude(id=rule_id).first()

                if existing_pair:
                    errors['from_item_id'] = Mess.ERROR_EXIST.value
                    errors['to_item_id'] = Mess.ERROR_EXIST.value
                    return JsonResponse({
                        'status': 'error',
                        'errors': errors,
                    })

                detailed_info.data_item_type_before = from_type_obj
                detailed_info.data_item_type_after = to_type_obj
                detailed_info.convert_rule = rule
                detailed_info.save()

                return JsonResponse({
                    'status': 'success',
                    'message': Mess.UPDATE.value
                })

        except Exception as e:
            logger.error(f"Error updating rule: {e}")
            return JsonResponse({
                'status': 'error',
                'message': Mess.ERROR.value
            }, status=500)


class RuleDeleteView(LoginRequiredMixin, View):
    def post(self, request, rule_id):
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request type'}, status=400)

        tenant = request.user.tenant
        try:
            detailed_info = get_object_or_404(DetailedInfo, id=rule_id, tenant=tenant)
            detailed_info.delete()

            return JsonResponse({
                'status': 'success',
                'message': Mess.DELETE.value
            })

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': Mess.ERROR.value
            }, status=500)
