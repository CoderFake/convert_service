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
    DataItemDeleteView,
    DataItemDetailView # Import the new view
)

urlpatterns = [
    path('settings/', ConfigsView.as_view(), name='settings'),
    path('settings/data-items/', DataItemListView.as_view(), name='data_items'),
    path('settings/data-item-create/', DataItemCreateView.as_view(), name='create_data_item'), # Handles POST for create
    path('settings/data-item-edit/<int:item_id>/', DataItemEditView.as_view(), name='edit_data_item'), # Handles POST for edit
    path('settings/data-item-detail/<int:item_id>/', DataItemDetailView.as_view(), name='detail_data_item'), # Handles GET for edit modal data
    path('settings/data-item-delete/<int:item_id>/', DataItemDeleteView.as_view(), name='delete_data_item'), # Handles POST for delete
    # path('settings/save-data-item/', SaveDataItemView.as_view(), name='save_data_item'), # This seems redundant now
    path('rule-settings/', RuleSettingsView.as_view(), name='rule_settings'),
    path('rule-settings/add-fixed-data/', AddFixedDataView.as_view(), name='add_fixed_data'),
    path('rule-settings/delete-fixed-data/', DeleteFixedDataView.as_view(), name='delete_fixed_data'),
    path('rule-settings/delete-rule/', DeleteRuleView.as_view(), name='delete_rule'),
    path('rule-settings/save-header-settings/', SaveHeaderSettingsView.as_view(), name='save_header_settings'),
]
