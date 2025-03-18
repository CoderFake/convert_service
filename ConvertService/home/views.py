from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.shortcuts import render
from django.http import JsonResponse
from process.redis import redis_client
import logging
from process.views import process_and_display, save_format_field

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

            if tab == "process-file":
                pass

            return render(request, 'web/home/index.html', context)

        return render(request, 'web/home/index.html')