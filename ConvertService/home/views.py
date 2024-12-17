from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import Http404, JsonResponse
from process.utils import get_redis_client
from home.dataclasses import PatientRecord
import json
import logging

logger = logging.getLogger(__name__)


@login_required
def get_processed_files(request):
    try:
        redis_client = get_redis_client()

        if request.method == "POST":
            body_data = json.loads(request.body.decode('utf-8'))
            request_key = body_data.get('request_key', 'processed:*')
            keys = redis_client.keys(request_key)

            if not keys:
                return JsonResponse({'status': 'error', 'message': '処理されたファイルが見つかりません。'})

            processed_data = []
            for key in keys:
                try:
                    raw_data = redis_client.get(key)
                    if raw_data:
                        data = json.loads(raw_data.decode('utf-8'))
                        processed_data.append({"key": key.decode('utf-8'), "data": data})
                except Exception as e:
                    logger.error(f"Error reading data from Redis key {key}: {e}")

            headers = list(PatientRecord.COLUMN_NAMES.values())
            return JsonResponse({'status': 'success', 'headers': headers, 'processed_files': processed_data})

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
