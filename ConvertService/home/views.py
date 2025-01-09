from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import JsonResponse
from accounts.models import Account
from home.ultis import HeaderFetcher, HeaderType, DisplayType
from process.utils import get_redis_client
import json
import logging

logger = logging.getLogger(__name__)



def filter_list(headers, hidden_headers, data):
    """
    Filter headers and data based on visible headers.
    """
    try:

        visible_indices = [i for i, header in enumerate(headers) if header not in hidden_headers]
        filtered_headers = [header for i, header in enumerate(headers) if i in visible_indices]

        filtered_data = []
        for row in data:
            if len(row) < len(headers):
                logger.warning(f"Skipping row due to mismatched length: {row}")
                continue
            try:
                filtered_row = [row[i] if i < len(row) else "" for i in visible_indices]
                filtered_data.append(filtered_row)
            except IndexError as e:
                logger.error(f"Error accessing row: {row}, error: {e}")
                continue

        return filtered_headers, filtered_data
    except Exception as e:
        logger.error(f"Error filtering data: {e}")
        return [], []



@login_required
def get_processed_files(request):
    """
    Fetch processed and formatted data from Redis, combine them, and return the result.
    """
    try:
        redis_client = get_redis_client()

        if request.method == "POST":
            input_keys = redis_client.keys("processed:*")
            format_keys = redis_client.keys("formatted:*")

            user = Account.objects.get(pk=request.user.id)
            first_headers = HeaderFetcher.get_headers(user, HeaderType.BEFORE.value, DisplayType.ALL.value)
            last_headers = HeaderFetcher.get_headers(user, HeaderType.FORMAT.value, DisplayType.ALL.value)
            first_hidden_headers = HeaderFetcher.get_headers(user, HeaderType.BEFORE.value, DisplayType.HIDDEN.value)
            last_hidden_headers = HeaderFetcher.get_headers(user, HeaderType.FORMAT.value, DisplayType.HIDDEN.value)

            if not input_keys or not format_keys:
                return JsonResponse({'status': 'error', 'message': '処理されたファイルが見つかりません。'})

            all_formatted_data = []
            formatted_keys = []
            try:
                for format_key in format_keys:
                    try:
                        raw_format_data = redis_client.get(format_key)
                        if raw_format_data:
                            format_data = json.loads(raw_format_data.decode('utf-8'))
                            all_formatted_data.append(format_data)
                            formatted_keys.append(format_key.decode('utf-8'))
                    except Exception as e:
                        logger.error(f"Error reading formatted data from Redis key {format_key}: {e}")
            except Exception as e:
                logger.error(f"Error combining formatted data: {e}")

            processed_data = []
            visible_headers = []

            for input_key, format_key in zip(input_keys, format_keys):
                try:
                    raw_input_data = redis_client.get(input_key)

                    if raw_input_data:
                        input_data = json.loads(raw_input_data.decode('utf-8'))

                        if isinstance(input_data, list) and all_formatted_data:
                            input_visible_headers, filtered_input_data = filter_list(
                                first_headers, first_hidden_headers, input_data
                            )

                            last_headers += ["予約確定日", "受付時間"]

                            format_visible_headers, filtered_format_data = filter_list(
                                last_headers, last_hidden_headers, all_formatted_data
                            )

                            if not visible_headers:
                                visible_headers = input_visible_headers + format_visible_headers

                            if filtered_input_data and filtered_format_data:
                                combined_data = [
                                    input_row + format_row
                                    for input_row, format_row in zip(filtered_input_data, filtered_format_data)
                                ]
                                processed_data.extend(combined_data)
                            else:
                                logger.warning(f"Skipping pair due to empty filtered data.")
                        else:
                            logger.error(f"Invalid data format for keys {input_key} and {format_key}")
                except Exception as e:
                    logger.error(f"Error reading or merging data from Redis keys {input_key} and {format_key}: {e}")

            return JsonResponse({
                'status': 'success',
                'headers': visible_headers,
                'processed_files': processed_data,
                'formatted_keys': formatted_keys
            })

        return JsonResponse({'status': 'error', "message": "無効なHTTPメソッドです。"})
    except Exception as e:
        logger.error(f"Error fetching processed files: {e}")
        return JsonResponse({'status': 'error', 'message': 'エラーが発生しました。'})


def home(request):
    if request.user.is_authenticated:
        tab = request.GET.get("tab", "upload-file")
        if tab not in ["upload-file", "process-file"]:
            tab = "upload-file"

        context = {"tab": tab}

        if tab == "process-file":
            pass

        return render(request, 'web/home/index.html', context)

    return render(request, 'web/home/index.html')
