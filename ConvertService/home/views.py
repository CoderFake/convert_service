from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import JsonResponse
from process.redis import redis_client
import logging
from process.views import process_and_display, save_format_field

logger = logging.getLogger(__name__)


@login_required
def get_processed_files(request):
    try:
        if request.method == "POST":
            process_and_display(request.session.session_key, request.user.id)
        return JsonResponse({'status': 'error', "message": "無効なHTTPメソッドです。"})
    except Exception as e:
        logger.error(f"Error fetching processed files: {e}")
        return JsonResponse({'status': 'error', 'message': 'エラーが発生しました。'})


@login_required
def update_format_data(request):
    try:
        if request.method == "POST":
            save_format_field(request)
        return JsonResponse({'status': 'error', 'message': '無効なHTTPメソッドです。'})
    except Exception as e:
        logger.error(f"Error updating format data: {e}")
        return JsonResponse({'status': 'error', 'message': 'エラーが発生しました。'})


def home(request):
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
