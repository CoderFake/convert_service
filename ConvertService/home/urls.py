from . import views

from django.urls import path
from accounts.urls import urlpatterns as account_urls
urlpatterns = [
    path('', views.home, name='home'),
    path('get-data/', views.get_processed_files, name='get_data'),
    path('update-format-data/', views.update_format_data, name='update_format_data')
] + account_urls