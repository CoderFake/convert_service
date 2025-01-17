import json
import os
from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from accounts.models import Account
from process.fetch_data import (
    HeaderFetcher,
    FileFormatFetcher,
    RuleFetcher,
    HeaderType,
    DisplayType,
    FixedValueFetcher
)
from .file_tasks import (
    process_and_format_file,
    process_multiple_files_task,
    generate_zip_task,
    generate_csv_task
)
from .utils import ProcessHeader, DisplayData
from .redis import redis_client
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    client = redis_client.get_client()
    client.set(f'{request.session.session_key}-file:{file_name}', file_path)

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

        client = redis_client.get_client()
        file_path = client.get(f'{request.session.session_key}-file:{file_name}')
        if file_path:
            os.remove(file_path.decode('utf-8'))
            client.delete(f'{request.session.session_key}-file:{file_name}')
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
        process_multiple_files_task.run(request.session.session_key,headers, file_format, mode)

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
        format_headers, edit_headers = HeaderFetcher.get_headers(user, HeaderType.FORMAT.value, DisplayType.ALL.value, edit=True)
        rules = RuleFetcher.get_rules(user, HeaderType.BEFORE.value, HeaderType.FORMAT.value)
        fixed_values = FixedValueFetcher.get_fixed_values(user)
        
        process_and_format_file.run(
            request.session.session_key,
            fixed_values,
            rules,
            before_headers,
            format_headers,
            user.tenant.id
        )

        return JsonResponse({
            "status": "success",
            "message": "データ処理がバックグラウンドで開始されました。結果は後ほど確認してください。"
        }, status=202)

    except Exception as e:
        logger.error(f"Error triggering data processing: {e}")
        return JsonResponse({"status": "error", "message": "データ処理中にエラーが発生しました。"}, status=500)


@login_required
def download_zip(request, zip_key="formatted:*"):
    try:
        client = redis_client.get_client()

        user = Account.objects.get(pk=request.user.id)
        headers = HeaderFetcher.get_headers(user, HeaderType.AFTER.value, DisplayType.SHOW.value)
        file_format = FileFormatFetcher.get_file_format_id(user, before=False)

        zip_key = generate_zip_task(zip_key, headers, file_format)

        if not zip_key:
            return redirect('home')

        zip_data = client.get(zip_key)
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
def download_csv(request, csv_key="output:*"):
    try:
        client = redis_client.get_client()

        user = Account.objects.get(pk=request.user.id)

        format_headers = HeaderFetcher.get_headers(user, HeaderType.FORMAT.value, DisplayType.ALL.value)
        output_headers = HeaderFetcher.get_headers(user, HeaderType.AFTER.value, DisplayType.ALL.value)
        rules = RuleFetcher.get_rules(user, HeaderType.FORMAT.value, HeaderType.AFTER.value)
        file_format = FileFormatFetcher.get_file_format_id(user, before=False)

        fixed_values = FixedValueFetcher.get_fixed_values(user)

        process_and_format_file.run(
            request.session.session_key,
            fixed_values,
            rules,
            format_headers,
            output_headers,
            user.tenant.id,
            type_keys="formatted:*"
        )

        csv_key = generate_csv_task(f"{request.session.session_key}-{csv_key}", output_headers, file_format)

        if not csv_key:
            return redirect('home')

        csv_data = client.get(csv_key)
        if not csv_data:
            messages.error(request, '指定されたCSVファイルが見つかりません。')
            return redirect('home')

        response = HttpResponse(csv_data, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{timezone.now().strftime("%Y%m%d")}_output.csv"'

        redis_client.delete_all_keys()
        return response
    except Exception as e:
        logger.error(f"Error downloading CSV file: {e}")
        return redirect('home')


def process_and_display(session_id, user_id):
    client = redis_client.get_client()
    user = Account.objects.get(pk=user_id)
    first_headers = HeaderFetcher.get_headers(user, HeaderType.BEFORE.value, DisplayType.ALL.value)
    last_headers, edit_headers = HeaderFetcher.get_headers(user, HeaderType.FORMAT.value, DisplayType.ALL.value, edit=True)

    first_hidden_headers = HeaderFetcher.get_headers(user, HeaderType.BEFORE.value, DisplayType.HIDDEN.value)
    last_hidden_headers = HeaderFetcher.get_headers(user, HeaderType.FORMAT.value, DisplayType.HIDDEN.value)
    
    input_keys = client.keys(f"{session_id}-processed:*")
    format_keys = client.keys(f"{session_id}-formatted:*")

    if not input_keys or not format_keys:
        logger.warning("No processed or formatted files found.")
        return {'status': 'error', 'message': '処理されたファイルが見つかりません。'}

    all_input_data, _ = DisplayData.get_list_data(client, input_keys)
    all_formatted_data, formatted_keys = DisplayData.get_list_data(client, format_keys)

    processed_data = []
    visible_headers = []

    def process_pair(input_key, format_key):
        try:
            if all_input_data and all_formatted_data:
                input_visible_headers, filtered_input_data = DisplayData.filter_list(
                    first_headers, first_hidden_headers, all_input_data
                )

                format_visible_headers, filtered_format_data = DisplayData.filter_list(
                    last_headers, last_hidden_headers, all_formatted_data
                )

                if not visible_headers:
                    visible_headers.extend(input_visible_headers + format_visible_headers)

                if filtered_input_data and filtered_format_data:
                    combined_data = [
                        input_row + format_row
                        for input_row, format_row in zip(filtered_input_data, filtered_format_data)
                    ]
                    return combined_data
                else:
                    logger.warning(f"Skipping pair due to empty filtered data.")
            return []
        except Exception as e:
            logger.error(f"Error reading or merging data from Redis keys {input_key} and {format_key}: {e}")
            return []

    max_workers = min(len(input_keys), os.cpu_count() or 1)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_pair, input_key, format_key): (input_key, format_key)
            for input_key, format_key in zip(input_keys, format_keys)
        }
        for future in as_completed(futures):
            try:
                combined_data = future.result()
                processed_data.extend(combined_data)
            except Exception as e:
                logger.error(f"Error in parallel processing: {e}")

    logger.info("Processed and formatted files combined successfully.")
    return JsonResponse({
        'status': "success",
        'headers': visible_headers,
        'processed_files': processed_data,
        'formatted_keys': formatted_keys,
        'edit_headers': edit_headers
    }, status=200)


def save_format_field(request):
    client = redis_client.get_client()

    key = request.POST.get('key')
    field_name = request.POST.get('field_name')
    field_value = request.POST.get('field_value')

    if not key or not field_name:
        return JsonResponse({'status': 'error', 'message': 'キーまたはフィールド名が提供されていません。'})

    raw_format_data = client.get(key)
    if not raw_format_data:
        return JsonResponse({'status': 'error', 'message': '指定されたキーが見つかりません。'})

    try:
        format_data = json.loads(raw_format_data.decode('utf-8'))
    except Exception as e:
        return JsonResponse(
            {'status': 'error', 'message': f'フォーマットデータの読み取り中にエラーが発生しました: {e}'})

    user = Account.objects.get(pk=request.user.id)
    header_names = HeaderFetcher.get_headers(user, HeaderType.FORMAT.value, DisplayType.ALL.value)

    if field_name not in header_names:
        return JsonResponse({'status': 'error', 'message': '指定されたフィールドが存在しません。'})

    header_index = header_names.index(field_name)

    if len(format_data) > header_index:
        format_data[header_index] = field_value
    else:
        return JsonResponse({'status': 'error', 'message': 'データの更新中にエラーが発生しました。'})
    try:
        redis_client.set(key, json.dumps(format_data))
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'フォーマットデータの更新中にエラーが発生しました: {e}'})

    return JsonResponse({'status': 'success', 'message': 'データが正常に更新されました。'})



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
