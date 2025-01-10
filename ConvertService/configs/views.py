from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from configs.models import ConvertRule
from home.models import FileFormat, DataItemType, DataItem, DataFormat, DetailedInfo, DataConversionInfo
from home.ultis import HeaderType


@login_required
def configs(request):
    format_list =  list(FileFormat.objects.all())
    return render(request, 'web/ settings/index.html', {'format_list': format_list})


def remove_bom(header_name):
    try:
        header = header_name.lstrip('\ufeff')
        header = header.replace("\ufeff", "")
    except Exception as e:
        return header_name
    return header


@login_required
def save_data_item(request):
    if request.method == 'POST':
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
                    data_item_type.edit_value =  bool(int(data_list.get(f"input[{header_name}][edit_value]", "0")))
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
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

        return JsonResponse({"status": "success", "message": "Data saved successfully!"}, status=200)

    return JsonResponse({"status": "error", "message": "Invalid request method"}, status=405)


@login_required
def rule_settings(request):
    if request.method == "POST":
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
                data_convert = DataConversionInfo.objects.filter(tenant=tenant, data_convert_id="C_001").first()

                detail_info = DetailedInfo.objects.filter(
                    tenant=tenant,
                    data_convert=data_convert,
                    data_item_id_before=data_item_input,
                    data_item_id_after=data_item_format,
                ).first()

                if detail_info:
                    return JsonResponse({"status": "error", "message": "Data item is exist"}, status=404)

                DetailedInfo.objects.create(
                    tenant=tenant,
                    data_convert=data_convert,
                    data_item_id_before=data_item_input,
                    data_item_id_after=data_item_format,
                    convert_rule=rule,
                )

            return JsonResponse({"status": "success", "message": "Rule saved successfully!"}, status=200)

        except DataItem.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Data item not found."}, status=404)
        except ConvertRule.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Convert rule not found."}, status=404)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

    data_inputs = DataItem.objects.filter(
        data_format__data_format_id="DF_003",
        tenant=request.user.tenant,
        data_item_types__type_name=HeaderType.BEFORE.value
    )

    data_formats = DataItem.objects.filter(
        data_format__data_format_id="DF_003",
        tenant=request.user.tenant,
        data_item_types__type_name=HeaderType.FORMAT.value
    )

    rule_list = ConvertRule.objects.all()

    context = {
        "data_inputs": data_inputs,
        "data_formats": data_formats,
        "rules": rule_list
    }

    return render(request, 'web/ settings/rule_settings.html', context)

