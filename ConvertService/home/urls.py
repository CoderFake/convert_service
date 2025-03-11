from django.urls import path
from .views import HomeView, ProcessedFilesView, UpdateFormatDataView
from accounts.urls import urlpatterns as account_urls

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('get-data/', ProcessedFilesView.as_view(), name='get_data'),
    path('update-format-data/', UpdateFormatDataView.as_view(), name='update_format_data')
] + account_urls