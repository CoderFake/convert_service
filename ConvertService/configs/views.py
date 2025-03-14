from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views import View
from configs.models import ConvertRule
from configs.utils import remove_bom
from home.models import FileFormat, DataItemType, DataItem, DataFormat, DetailedInfo, DataConversionInfo
from process.fetch_data import HeaderType


class ConfigsView(LoginRequiredMixin, View):
    def get(self, request):
        format_list = list(FileFormat.objects.all())
        return render(request, 'web/settings/index.html', {'format_list': format_list})


class SaveDataItemView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            data = request.POST

            data_format = DataFormat.objects.filter(tenant=request.user.tenant, data_format_id="DF_003").first()
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
                    print(f"Error processing key {key}: {e}")

            data_item_types = DataItemType.objects.filter(
                data_item__tenant=request.user.tenant,
                data_item__data_format=data_format
            )

            for data_item_type in data_item_types:

                header_name = data_item_type.data_item.data_item_name
                if data_item_type.type_name == 'input':
                    data_item_type.index_value = int(data_list.get(f"input[{header_name}][index]", "0"))
                    data_item_type.display = bool(int(data_list.get(f"input[{header_name}][display]", "0")))
                    data_item_type.edit_value = bool(int(data_list.get(f"input[{header_name}][edit_value]", "0")))
                    data_item_type.format_value = data_list.get(f"input[{header_name}][format_value]", "string")
                elif data_item_type.type_name == 'format':
                    data_item_type.index_value = int(data_list.get(f"format[{header_name}][index]", "0"))
                    data_item_type.display = bool(int(data_list.get(f"format[{header_name}][display]")))
                    data_item_type.edit_value = bool(int(data_list.get(f"format[{header_name}][edit_value]", "0")))
                    data_item_type.format_value = data_list.get(f"format[{header_name}][format_value]", "string")
                elif data_item_type.type_name == 'output':
                    data_item_type.index_value = int(data_list.get(f"output[{header_name}][index]", "0"))
                    data_item_type.display = bool(int(data_list.get(f"output[{header_name}][display]")))
                    data_item_type.edit_value = bool(int(data_list.get(f"output[{header_name}][edit_value]", "0")))
                    data_item_type.format_value = data_list.get(f"output[{header_name}][format_value]", "string")

                try:
                    data_item_type.save()
                    print("Saved successfully")
                except Exception as e:
                    print(f"Save error: {e}")

            return JsonResponse({"status": "success", "message": "Data saved successfully!"}, status=200)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)


class RuleSettingsView(LoginRequiredMixin, View):
    def get(self, request):
        input = request.GET.get('before', 'input')
        output = request.GET.get('after', 'output')

        if input == HeaderType.BEFORE.value:
            data_input = HeaderType.BEFORE.value
        elif input == HeaderType.FORMAT.value:
            data_input = HeaderType.FORMAT.value
        else:
            messages.error(request, "Data not found.")
            return redirect(f"{reverse('rule_settings')}?before=input&after=format")

        data_output = HeaderType.FORMAT.value
        if output == HeaderType.BEFORE.value:
            if input == HeaderType.FORMAT.value:
                data_output = HeaderType.BEFORE.value
            else:
                messages.error(request, "Data not found.")
                return redirect(f"{reverse('rule_settings')}?before=input&after=format")
        elif output == HeaderType.AFTER.value:
            if input == HeaderType.FORMAT.value:
                data_output = HeaderType.AFTER.value
            else:
                messages.error(request, "Data not found.")
                return redirect(f"{reverse('rule_settings')}?before=format&after=output")

        data_inputs = DataItem.objects.filter(
            data_format__data_format_id="DF_003",
            tenant=request.user.tenant,
            data_item_types__type_name=data_input
        ).annotate(
            index_value=F('data_item_types__index_value')
        ).order_by('index_value')

        data_formats = DataItem.objects.filter(
            data_format__data_format_id="DF_003",
            tenant=request.user.tenant,
            data_item_types__type_name=data_output
        ).annotate(
            index_value=F('data_item_types__index_value')
        ).order_by('index_value')

        rule_list = ConvertRule.objects.all()

        context = {
            'data_inputs': data_inputs,
            'data_formats': data_formats,
            'rules': rule_list,
        }

        return render(request, 'web/settings/rule_settings.html', context)

    def post(self, request):
        input = request.GET.get('before', 'input')
        output = request.GET.get('after', 'output')

        try:
            with transaction.atomic():
                data = request.POST
                tenant = request.user.tenant
                rule_id = data.get("rule_name")
                data_item_input_id = data.get("data_item_input")
                data_item_format_id = data.get("data_item_format")

                rule = ConvertRule.objects.get(id=rule_id)
                data_item_input = DataItem.objects.get(id=data_item_input_id, tenant=tenant)
                data_item_format = DataItem.objects.get(id=data_item_format_id, tenant=tenant)
                data_convert = DataConversionInfo.objects.filter(
                    tenant=tenant,
                    data_convert_id="C_001"
                ).first()

                if input == HeaderType.BEFORE.value:
                    data_input = HeaderType.BEFORE.value
                elif input == HeaderType.FORMAT.value:
                    data_input = HeaderType.FORMAT.value
                else:
                    messages.error(request, "Data not found.")
                    return redirect(f"{reverse('rule_settings')}?before=input&after=format")

                data_output = HeaderType.FORMAT.value
                if output == HeaderType.BEFORE.value:
                    if input == HeaderType.FORMAT.value:
                        data_output = HeaderType.BEFORE.value
                    else:
                        messages.error(request, "Data not found.")
                        return redirect(f"{reverse('rule_settings')}?before=input&after=format")
                elif output == HeaderType.AFTER.value:
                    if input == HeaderType.FORMAT.value:
                        data_output = HeaderType.AFTER.value
                    else:
                        messages.error(request, "Data not found.")
                        return redirect(f"{reverse('rule_settings')}?before=format&after=output")

                data_item_type_before = DataItemType.objects.get(
                    data_item=data_item_input,
                    type_name=data_input
                )

                data_item_type_after = DataItemType.objects.get(
                    data_item=data_item_format,
                    type_name=data_output
                )

                detail_info = DetailedInfo.objects.filter(
                    tenant=tenant,
                    data_convert=data_convert,
                    data_item_type_id_before=data_item_type_before,
                    data_item_type_id_after=data_item_type_after,
                ).first()

                if detail_info:
                    detail_info.convert_rule = rule
                    detail_info.save()
                    messages.success(request, "Rule updated successfully!")
                    return redirect(f"{reverse('rule_settings')}?before={input}&after={output}")

                DetailedInfo.objects.create(
                    tenant=tenant,
                    data_convert=data_convert,
                    data_item_type_id_before=data_item_type_before,
                    data_item_type_id_after=data_item_type_after,
                    convert_rule=rule,
                )
                messages.success(request, "Rule saved successfully!")
                return redirect(f"{reverse('rule_settings')}?before={input}&after={output}")

        except DataItem.DoesNotExist:
            messages.error(request, "Data item not found.")
            return redirect(f"{reverse('rule_settings')}?before={input}&after={output}")
        except DataItemType.DoesNotExist:
            messages.error(request, "Data item type not found.")
            return redirect(f"{reverse('rule_settings')}?before={input}&after={output}")
        except ConvertRule.DoesNotExist:
            messages.error(request, "Convert rule not found.")
            return redirect(f"{reverse('rule_settings')}?before={input}&after={output}")
        except Exception as e:
            messages.error(request, str(e))
            return redirect(f"{reverse('rule_settings')}?before={input}&after={output}")