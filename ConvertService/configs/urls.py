from django.urls import path
from .views import (
    ConfigsView,
    SaveDataItemView,
    RuleSettingsView,
    AddFixedDataView,
    DeleteFixedDataView,
    DeleteRuleView,
    SaveHeaderSettingsView,
    DataItemListView,
    DataItemCreateView,
    DataItemEditView,
    DataItemDeleteView
)

urlpatterns = [
    path('settings/', ConfigsView.as_view(), name='settings'),
    path('settings/data-items/', DataItemListView.as_view(), name='data_items'),
    path('settings/data-item-create/', DataItemCreateView.as_view(), name='create_data_item'),
    path('settings/data-item-edit/<str:id>', DataItemEditView.as_view(), name='edit_data_item'),
    path('settings/data-item-delete/<str:id>', DataItemDeleteView.as_view(), name='delete_data_item'),
    path('settings/save-data-item/', SaveDataItemView.as_view(), name='save_data_item'),
    path('rule-settings/', RuleSettingsView.as_view(), name='rule_settings'),
    path('rule-settings/add-fixed-data/', AddFixedDataView.as_view(), name='add_fixed_data'),
    path('rule-settings/delete-fixed-data/', DeleteFixedDataView.as_view(), name='delete_fixed_data'),
    path('rule-settings/delete-rule/', DeleteRuleView.as_view(), name='delete_rule'),
    path('rule-settings/save-header-settings/', SaveHeaderSettingsView.as_view(), name='save_header_settings'),
]