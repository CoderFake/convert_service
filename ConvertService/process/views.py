import json
import math
import os
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views import View
from accounts.models import Account
from process.fetch_data import (
    HeaderFetcher,
    FileFormatFetcher,
    RuleFetcher,
    HeaderType,
    DisplayType
)
from .data_type import DownloadType
from .file_tasks import (
    process_and_format_file,
    process_multiple_files_task,
    generate_zip_task,
    generate_csv_task
)
from .utils import ProcessHeader, DisplayData
from .redis import redis_client
import logging

logger = logging.getLogger(__name__)


class UploadFileView(LoginRequiredMixin, View):
    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return JsonResponse({'status': 'error', 'message': 'ファイルが提供されていません。'})

        file_name = file.name
        file_path = os.path.join('/tmp', file_name)

        with open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)

        user = Account.objects.get(pk=request.user.id)
        allowed_formats = FileFormatFetcher.get_allowed_formats_for_tenant(user.tenant.id)

        file_extension = os.path.splitext(file_name)[1].lower()
        content_type = file.content_type

        if not FileFormatFetcher.is_valid_file_type(content_type, file_extension, allowed_formats):
            return JsonResponse({'status': 'error', 'message': f'無効なファイルタイプ: {file_name}。'})

        if file.size > 5 * 1024 * 1024:
            return JsonResponse({'status': 'error', 'message': f'ファイルサイズが制限を超えています: {file_name}。'})
        client = redis_client.get_client()
        client.set(f'{request.session.session_key}-file:{file_name}', file_path)

        file_format = FileFormatFetcher.get_file_format_for_content_type(content_type, file_extension)
        client.set(f'{request.session.session_key}-file-format:{file_name}', file_format, ex=3600)

        return JsonResponse({'status': 'success', 'message': f'ファイルがアップロードされました: {file_name}。'})


class DeleteFileView(LoginRequiredMixin, View):
    def post(self, request):
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


class ProcessFilesView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            user = Account.objects.get(pk=request.user.id)
            headers = HeaderFetcher.get_headers(user, HeaderType.BEFORE.value, DisplayType.ALL.value)
            process_multiple_files_task.run(request.session.session_key, headers)

            return JsonResponse({
                'status': 'success',
                'message': 'File processing started.'
            })
        except Exception as e:
            logger.error(f"Error starting file processing task: {e}")
            return JsonResponse({'status': 'error', 'message': f'エラー: {str(e)}'})


class FormatDataProcessingView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            user = Account.objects.get(pk=request.user.id)
            before_headers = HeaderFetcher.get_headers(user, HeaderType.BEFORE.value, DisplayType.ALL.value,
                                                       get_edit_header=True)
            format_headers = HeaderFetcher.get_headers(user, HeaderType.FORMAT.value, DisplayType.ALL.value)
            rules = RuleFetcher.get_rules(user, HeaderType.BEFORE.value, HeaderType.FORMAT.value)

            process_and_format_file.run(
                request.session.session_key,
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


class DownloadZipView(LoginRequiredMixin, View):
    def get(self, request, zip_key="formatted:*"):
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


class DownloadView(LoginRequiredMixin, View):
    def get(self, request, download_type=DownloadType.SYSTEM.value):
        if download_type not in [down_type.value for down_type in DownloadType]:
            messages.error(request, '無効なダウンロードタイプです。')
            return redirect('home')

        try:
            client = redis_client.get_client()

            user = Account.objects.get(pk=request.user.id)
            if download_type == DownloadType.SYSTEM.value:
                format_headers = HeaderFetcher.get_headers(user, HeaderType.FORMAT.value, DisplayType.SHOW.value,
                                                           get_edit_header=True)
                output_headers = HeaderFetcher.get_headers(user, HeaderType.AFTER.value, DisplayType.ALL.value)
                rules = RuleFetcher.get_rules(user, HeaderType.FORMAT.value, HeaderType.AFTER.value)
            else:
                format_headers = HeaderFetcher.get_headers(user, HeaderType.FORMAT.value, DisplayType.ALL.value,
                                                           get_edit_header=True)
                output_headers = HeaderFetcher.get_headers(user, HeaderType.BEFORE.value, DisplayType.ALL.value)
                rules = RuleFetcher.get_rules(user, HeaderType.FORMAT.value, HeaderType.BEFORE.value)

            file_format = FileFormatFetcher.get_file_format_id(user, before=False)

            process_and_format_file.run(
                request.session.session_key,
                rules,
                format_headers,
                output_headers,
                user.tenant.id,
                type_keys="formatted:*"
            )

            csv_key = generate_csv_task(f"{request.session.session_key}-output:*", output_headers, file_format)

            if not csv_key:
                return redirect('home')

            csv_data = client.get(csv_key)
            if not csv_data:
                messages.error(request, '指定されたCSVファイルが見つかりません。')
                return redirect('home')

            response = HttpResponse(csv_data, content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{timezone.now().strftime("%Y%m%d_%H%M%S")}_{download_type}_output.csv"'

            return response
        except Exception as e:
            logger.error(f"Error downloading CSV file: {e}")
            return redirect('home')


class ProcessAndDisplayView:
    @staticmethod
    def process_and_display(session_id, user_id, request=None):
        try:
            page = 1
            page_size = 20

            if request and request.method == 'POST':
                try:
                    data = json.loads(request.body.decode('utf-8'))
                    page = int(data.get('page', 1))
                    page_size = int(data.get('page_size', 20))
                except json.JSONDecodeError:
                    pass
                except ValueError:
                    pass

            page = max(1, page)
            page_size = max(10, min(100, page_size))

            client = redis_client.get_client()

            user = Account.objects.get(pk=user_id)

            show_formatted_header = HeaderFetcher.get_headers(
                user,
                HeaderType.FORMAT.value,
                DisplayType.SHOW.value,
                get_edit_header=True
            )

            hidden_formatted_header = HeaderFetcher.get_headers(
                user,
                HeaderType.FORMAT.value,
                DisplayType.HIDDEN.value,
                get_edit_header=True
            )

            format_keys = client.keys(f"{session_id}-formatted:*")

            if not format_keys:
                logger.warning("Không tìm thấy dữ liệu đã được xử lý.")
                return JsonResponse({
                    'status': 'error',
                    'message': '処理されたファイルが見つかりません。'
                }, status=404)

            processed_data, total_rows = DisplayData.get_paginated_data(
                client,
                format_keys,
                hidden_formatted_header,
                page,
                page_size
            )

            total_pages = math.ceil(total_rows / page_size) if total_rows > 0 else 0

            return JsonResponse({
                'status': "success",
                'headers': show_formatted_header,
                'data': processed_data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_pages': total_pages,
                    'total_rows': total_rows
                }
            }, status=200)

        except Exception as e:
            logger.error(f"Lỗi trong process_and_display: {e}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)


class SaveFormatFieldView:
    @staticmethod
    def save_format_field(request):
        client = redis_client.get_client()

        key = request.POST.get('key')
        field_name = request.POST.get('field_name')
        field_value = request.POST.get('field_value')

        if not key or not field_name:
            return JsonResponse({'status': 'error', 'message': 'キーまたはフィールド名が提供されていません。'})

        try:
            input_key = key.split(' ')[0]
            index = int(key.split(' ')[1])
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': 'キーの解析中にエラーが発生しました。'})

        raw_format_data = client.get(input_key)
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

        if len(format_data[index]) > header_index:
            format_data[index][header_index] = field_value
        else:
            return JsonResponse({'status': 'error', 'message': 'データの更新中にエラーが発生しました。'})
        try:
            client.set(input_key, json.dumps(format_data))
        except Exception as e:
            return JsonResponse(
                {'status': 'error', 'message': f'フォーマットデータの更新中にエラーが発生しました: {e}'})

        return JsonResponse({'status': 'success', 'message': 'データが正常に更新されました。'})


class ProcessHeadersView(LoginRequiredMixin, View):
    def post(self, request):
        uploaded_files, error = self.get_uploaded_files(request)
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

    def get_uploaded_files(self, request):
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


def process_and_display(session_id, user_id, request=None):
    return ProcessAndDisplayView.process_and_display(session_id, user_id, request)


def save_format_field(request):
    return SaveFormatFieldView.save_format_field(request)