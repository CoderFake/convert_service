from . import views

from django.urls import path
from accounts.urls import urlpatterns as account_urls
urlpatterns = [
    path('', views.home, name='home')
] + account_urls