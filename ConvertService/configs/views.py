from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from home.models import FileFormat, DataItemType, DataItem, DataFormat


@login_required
def configs(request):
    format_list =  list(FileFormat.objects.all())
    return render(request, 'web/ settings/index.html', {'format_list': format_list})


def remove_bom(header_name):
    try:
        header = header_name.lstrip('\ufeff')
    except Exception as e:
        return header_name
    return header


@login_required
@transaction.atomic
def save_data_item(request):
    if request.method == 'POST':
        try:
            data = request.POST

            data_format = DataFormat.objects.filter(tenant=request.user.tenant, data_format_id="DF_003").first()

            for key in data.keys():
                if key.startswith('input') or key.startswith('format') or key.startswith('output'):
                    header_name = remove_bom(key.split('[')[1].split(']')[0])
                    field_type = key.split('[')[0]
                    field_attr = key.split('[')[2].split(']')[0]

                    data_item, _ = DataItem.objects.get_or_create(
                        data_format=data_format,
                        tenant=request.user.tenant,
                        data_item_name=header_name,
                        defaults={
                            'data_item_id': f"D000{DataItem.objects.count() + 1}"
                        }
                    )

                    try:
                        item_type = DataItemType.objects.get(
                            data_item=data_item,
                            type_name=field_type
                        )
                    except DataItemType.DoesNotExist:
                        item_type = DataItemType.objects.create(
                            data_item=data_item,
                            type_name=field_type,
                        )

                    if field_attr == 'display':
                        item_type.display = bool(int(data.get(key)))
                    elif field_attr == 'type':
                        item_type.format_value = data.get(key)
                    elif field_attr == 'index':
                        item_type.index_value = int(data.get(key))
                    elif field_attr == 'edit':
                        item_type.edit_value = bool(int(data.get(key)))
            return JsonResponse({"status": "success", "message": "Data saved successfully!"}, status=200)

        except Exception as e:
            return JsonResponse({"status": "error", "message": f"Failed to save data: {str(e)}"}, status=400)

    return JsonResponse({"status": "error", "message": "Invalid request method"}, status=405)
