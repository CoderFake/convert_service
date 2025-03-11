from django.urls import path
from .views import ConfigsView, SaveDataItemView, RuleSettingsView

urlpatterns = [
    path('settings/', ConfigsView.as_view(), name='settings'),
    path('settings/save-data-item/', SaveDataItemView.as_view(), name='save_data_item'),
    path('rule-settings/', RuleSettingsView.as_view(), name='rule_settings'),
]