from django.urls import path
from . import views

urlpatterns = [
    path('settings/', views.configs, name='settings'),
    path('settings/save-data-item/', views.save_data_item, name='save_data_item'),
]