from django.urls import path
from . import views

urlpatterns = [
    path('upload-file/', views.upload_file, name='upload_file'),
    path('delete-file/', views.delete_file, name='delete_file'),
    path('process-files/', views.process_files, name='process_files'),
    path('download-zip/<str:zip_key>/', views.download_zip, name='download_zip'),
]