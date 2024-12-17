import json
import os
from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from home.dataclasses import PatientRecord
from .file_tasks import process_and_format_file, process_multiple_files_task, generate_zip_task
from .utils import get_redis_client
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
            return JsonResponse({'status': 'error', 'message': "無効なモードです。 'csv' または 'dict' を選択してください。"})

        process_multiple_files_task.run(mode)

        return JsonResponse({
            'status': 'success',
            'message': 'File processing started.'
        })
    except Exception as e:
        logger.error(f"Error starting file processing task: {e}")
        return JsonResponse({'status': 'error', 'message': f'エラー: {str(e)}'})


# @login_required
# def process_files(request):
#     if request.method != 'POST':
#         return JsonResponse({'status': 'error', 'message': '無効なHTTPメソッドです。'})
#
#     try:
#         redis_client = get_redis_client()
#
#         keys = redis_client.keys('file:*')
#         if not keys:
#             return JsonResponse({'status': 'error', 'message': '処理するファイルがありません。'})
#
#         zip_buffer = io.BytesIO()
#         output_files = []
#
#         def process_and_convert(file_path, key):
#             try:
#                 file_path = Path(file_path)
#                 output_csv_path = file_path.with_suffix('.csv')
#                 FileProcessor.process_file(file_path, output_csv_path)
#
#                 if output_csv_path.exists():
#                     redis_client.delete(key)
#                     return output_csv_path
#                 return None
#             except Exception as e:
#                 logger.error(f"Error processing file {file_path}: {e}")
#                 return None
#
#         max_workers = os.cpu_count() or 1
#         logger.info(f"Using max_workers={max_workers} for ThreadPoolExecutor")
#
#         with ThreadPoolExecutor(max_workers=max_workers) as executor:
#             futures = {
#                 executor.submit(process_and_convert, redis_client.get(key).decode('utf-8'), key): key
#                 for key in keys
#             }
#
#             for future in as_completed(futures):
#                 result = future.result()
#                 if result:
#                     output_files.append(result)
#
#         with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
#             for file in output_files:
#                 with open(file, 'rb') as f:
#                     zip_file.writestr(file.name, f.read())
#
#         zip_buffer.seek(0)
#
#         zip_key = f'zip:{base64.urlsafe_b64encode(os.urandom(6)).decode("utf-8")}'
#         redis_client.set(zip_key, zip_buffer.getvalue(), ex=3600)
#
#         return JsonResponse({'status': 'success', 'key': zip_key})
#     except Exception as e:
#         return JsonResponse({'status': 'error', 'message': f'ファイルの処理中にエラーが発生しました: {str(e)}'})


@login_required
def format_data_processing(request):
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "無効なHTTPメソッドです。"}, status=405)

    try:
        body_data = json.loads(request.body.decode('utf-8'))
        data_convert_id = body_data.get('data_convert_id')

        if not data_convert_id:
            return JsonResponse({"status": "error", "message": "必須パラメータ 'data_convert_id' が不足しています。"})

        result = process_and_format_file.run(data_convert_id)

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
        zip_key = generate_zip_task(zip_key, PatientRecord.COLUMN_NAMES.values())

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