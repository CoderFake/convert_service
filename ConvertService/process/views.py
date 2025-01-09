import json
import os
from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from accounts.models import Account
from home.ultis import (
    HeaderFetcher,
    FileFormatFetcher,
    RuleFetcher,
    HeaderType,
    DisplayType
)
from .file_tasks import (
    process_and_format_file,
    process_multiple_files_task,
    generate_zip_task,
    generate_csv_task
)
from .utils import get_redis_client, ProcessHeader
import logging

logger = logging.getLogger(__name__)


@login_required
def upload_file(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': '無効なHTTPメソッドです。'})

    file = request.FILES.get('file')
    if not file:
        return JsonResponse({'status': 'error', 'message': 'ファイルが提供されていません。'})

    file_name = file.name
    file_path = os.path.join('/tmp', file_name)

    with open(file_path, 'wb+') as destination:
        for chunk in file.chunks():
            destination.write(chunk)

    valid_types = [
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/json',
        'application/csv',
        'application/xml',
        'text/xml',
        'application/pdf',
        'text/csv'
    ]
    if file.content_type not in valid_types:
        return JsonResponse({'status': 'error', 'message': f'無効なファイルタイプ: {file_name}。'})

    if file.size > 5 * 1024 * 1024:
        return JsonResponse({'status': 'error', 'message': f'ファイルサイズが制限を超えています: {file_name}。'})

    redis_client = get_redis_client()
    redis_client.set(f'file:{file_name}', file_path)

    return JsonResponse({'status': 'success', 'message': f'ファイルがアップロードされました: {file_name}。'})


@login_required
def delete_file(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': '無効なHTTPメソッドです。'})

    try:
        data = json.loads(request.body)
        file_name = data.get('file_name')

        if not file_name:
            return JsonResponse({'status': 'error', 'message': 'ファイル名が指定されていません。'})

        redis_client = get_redis_client()
        file_path = redis_client.get(f'file:{file_name}')
        if file_path:
            os.remove(file_path.decode('utf-8'))
            redis_client.delete(f'file:{file_name}')
            return JsonResponse({'status': 'success', 'message': f'ファイルが削除されました: {file_name}。'})

        return JsonResponse({'status': 'error', 'message': f'Redisにファイルが見つかりません: {file_name}。'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'ファイルの削除中にエラーが発生しました: {str(e)}'})


@login_required
def process_files(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': '無効なHTTPメソッドです。'})

    try:
        body_data = json.loads(request.body.decode('utf-8'))
        mode = body_data.get('mode', 'dict')

        if mode not in ['csv', 'dict']:
            return JsonResponse(
                {'status': 'error', 'message': "無効なモードです。 'csv' または 'dict' を選択してください。"})

        user = Account.objects.get(pk=request.user.id)
        headers = HeaderFetcher.get_headers(user, HeaderType.BEFORE.value, DisplayType.ALL.value)
        file_format = FileFormatFetcher.get_file_format_id(user, before=True)
        process_multiple_files_task.run(headers, file_format, mode)

        return JsonResponse({
            'status': 'success',
            'message': 'File processing started.'
        })
    except Exception as e:
        logger.error(f"Error starting file processing task: {e}")
        return JsonResponse({'status': 'error', 'message': f'エラー: {str(e)}'})


@login_required
def format_data_processing(request):
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "無効なHTTPメソッドです。"}, status=405)

    try:
        user = Account.objects.get(pk=request.user.id)

        before_headers = HeaderFetcher.get_headers(user, HeaderType.BEFORE.value, DisplayType.ALL.value)
        format_headers = HeaderFetcher.get_headers(user, HeaderType.FORMAT.value, DisplayType.ALL.value)
        rules = RuleFetcher.get_rules(user, HeaderType.BEFORE.value, HeaderType.FORMAT.value)

        result = process_and_format_file.run(rules, before_headers, format_headers, request.user.tenant.id)

        return JsonResponse({
            "status": "success",
            "message": result
        }, status=200)

    except Exception as e:
        logger.error(f"Error triggering data processing: {e}")
        return JsonResponse({"status": "error", "message": "データ処理中にエラーが発生しました。"}, status=500)


@login_required
def download_zip(request, zip_key="formatted:*"):
    try:
        redis_client = get_redis_client()

        user = Account.objects.get(pk=request.user.id)
        headers = HeaderFetcher.get_headers(user, HeaderType.AFTER.value, DisplayType.SHOW.value)
        file_format = FileFormatFetcher.get_file_format_id(user, before=False)

        zip_key = generate_zip_task(zip_key, headers, file_format)

        if not zip_key:
            return redirect('home')

        zip_data = redis_client.get(zip_key)
        if not zip_data:
            messages.error(request, '指定されたZIPファイルが見つかりません。')
            return redirect('home')

        response = HttpResponse(zip_data, content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{timezone.now().strftime("%Y%m%d")}_output.zip"'
        return response
    except Exception as e:
        logger.error(f"Error downloading ZIP file: {e}")
        return redirect('home')


@login_required
def download_csv(request, zip_key="formatted:*"):
    try:
        redis_client = get_redis_client()

        user = Account.objects.get(pk=request.user.id)
        headers = HeaderFetcher.get_headers(user, HeaderType.AFTER.value, DisplayType.SHOW.value)
        file_format = FileFormatFetcher.get_file_format_id(user, before=False)

        csv_key = generate_csv_task(zip_key, headers, file_format)

        if not csv_key:
            return redirect('home')

        csv_data = redis_client.get(csv_key)
        if not csv_data:
            messages.error(request, '指定されたCSVファイルが見つかりません。')
            return redirect('home')

        response = HttpResponse(csv_data, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{timezone.now().strftime("%Y%m%d")}_output.csv"'
        return response
    except Exception as e:
        logger.error(f"Error downloading CSV file: {e}")
        return redirect('home')


def get_uploaded_files(request):
    input_file = request.FILES.get('input-file')
    format_file = request.FILES.get('format-file')
    output_file = request.FILES.get('output-file')

    if not input_file or not format_file or not output_file:
        return None, 'すべてのファイル (input-file, format-file, output-file) を提供してください。'

    input_type = request.POST.get('input-type', '').strip()
    format_type = request.POST.get('format-type', '').strip()
    output_type = request.POST.get('output-type', '').strip()

    if not input_type or not format_type or not output_type:
        return None, 'すべてのファイル形式 (input-type, format-type, output-type) を選択してください。'
    uploaded_files = []

    for file, file_type in [(input_file, input_type), (format_file, format_type), (output_file, output_type)]:
        uploaded_files.append((file, file_type))

    return uploaded_files, None


@login_required
def process_headers(request):
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "POST メソッドのみ許可されています。"}, status=405)

    uploaded_files, error = get_uploaded_files(request)
    if error:
        return JsonResponse({"status": "error", "message": error}, status=400)

    structured_data = {}

    for idx, (file, file_type) in enumerate(uploaded_files):
        try:
            headers = ProcessHeader.get_header(file, file_type)
            if headers:
                for i, header in enumerate(headers):
                    if header not in structured_data:
                        structured_data[header] = {
                            "input": None,
                            "format": None,
                            "output": None
                        }

                    data_type = "string"
                    display = 0 if idx == 0 else 1

                    if idx == 0:
                        structured_data[header]["input"] = {
                            "display": display,
                            "type": data_type,
                            "index": i
                        }
                    elif idx == 1:
                        structured_data[header]["format"] = {
                            "display": display,
                            "type": data_type,
                            "index": i
                        }
                    elif idx == 2:
                        structured_data[header]["output"] = {
                            "display": display,
                            "type": data_type,
                            "index": i
                        }

        except Exception as e:
            logger.error(f"Error processing file {file.name}: {e}")

    return JsonResponse({
        "status": "success",
        "structured_data": structured_data
    })
