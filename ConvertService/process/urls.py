from django.urls import path
from . import views

urlpatterns = [
    path('upload-file/', views.UploadFileView.as_view(), name='upload_file'),
    path('delete-file/', views.DeleteFileView.as_view(), name='delete_file'),
    path('process-files/', views.ProcessFilesView.as_view(), name='process_files'),
    path('process-headers/', views.ProcessHeadersView.as_view(), name='process_headers'),
    path('file-format/', views.FormatDataProcessingView.as_view(), name='format_data_processing'),
    path('download-zip/<str:zip_key>/', views.DownloadZipView.as_view(), name='download_zip'),
    path('download/<str:download_type>/', views.DownloadView.as_view(), name='download'),
]