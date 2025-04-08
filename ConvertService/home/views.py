from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views import View
from django.shortcuts import render, redirect
from django.http import JsonResponse

from process.fetch_data import FileFormatFetcher
from process.redis import redis_client
import logging
from process.views import process_and_display, save_format_field
from configs.utils import get_edit_options

logger = logging.getLogger(__name__)


class ProcessedFilesView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            return process_and_display(request.session.session_key, request.user.id, request)
        except Exception as e:
            logger.error(f"Error fetching processed files: {e}")
            return JsonResponse({'status': 'error', 'message': 'エラーが発生しました。'})


class UpdateFormatDataView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            save_format_field(request)
            return JsonResponse({'status': 'success', 'message': 'データが正常に更新されました。'})
        except Exception as e:
            logger.error(f"Error updating format data: {e}")
            return JsonResponse({'status': 'error', 'message': 'エラーが発生しました。'})


class HomeView(View):
    def get(self, request):
        if request.user.is_authenticated:
            tab = request.GET.get("tab", "upload-file")
            if tab not in ["upload-file", "process-file"]:
                tab = "upload-file"

            if tab == "upload-file":
                redis_client.delete_all_keys()
                context = {"tab": tab}
            elif tab == "process-file":
                context = {"tab": tab}

                client = redis_client.get_client()
                file_keys = client.keys(f'{request.session.session_key}-file:*')

                data_format_id = None
                if file_keys:
                    first_file_key = file_keys[0].decode('utf-8').split(':')[1]
                    file_format_key = f'{request.session.session_key}-file-format:{first_file_key}'
                    file_format = client.get(file_format_key)

                    if file_format:
                        file_format = file_format.decode('utf-8')
                        data_format_id = FileFormatFetcher.get_data_format_id_for_file_format(file_format)

                context["edit_options"] = get_edit_options(data_format_id)
            else:
                context = {"tab": "upload-file"}

            return render(request, 'web/home/index.html', context)

        return redirect(reverse('login'))


class GetEditOptionsView(LoginRequiredMixin, View):
    def get(self, request):
        try:
            client = redis_client.get_client()
            file_keys = client.keys(f'{request.session.session_key}-file:*')

            data_format_id = None
            if file_keys:
                first_file_key = file_keys[0].decode('utf-8').split(':')[1]
                file_format_key = f'{request.session.session_key}-file-format:{first_file_key}'
                file_format = client.get(file_format_key)

                if file_format:
                    file_format = file_format.decode('utf-8')
                    data_format_id = FileFormatFetcher.get_data_format_id_for_file_format(file_format)

            options = get_edit_options(data_format_id)
            return JsonResponse({'status': 'success', 'options': options})
        except Exception as e:
            logger.error(f"Error fetching edit options: {e}")
            return JsonResponse({'status': 'error', 'message': 'エラーが発生しました。'})
