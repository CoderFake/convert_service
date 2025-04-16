from django.urls import path
from .views import (
    DataItemListView,
    DataItemCreateView,
    DataItemEditView,
    DataItemDeleteView,
    DataItemDetailView,
    RuleSettingsView,
    RuleDetailView,
    RuleCreateView,
    RuleEditView,
    RuleDeleteView,
    GetItemsView
)

urlpatterns = [
    path('settings/data-items/', DataItemListView.as_view(), name='data_items'),
    path('settings/data-item-create/', DataItemCreateView.as_view(), name='create_data_item'),
    path('settings/data-item-edit/<int:item_id>/', DataItemEditView.as_view(), name='edit_data_item'),
    path('settings/data-item-detail/<int:item_id>/<str:file_format_id>/<str:data_item_type_name>/',
         DataItemDetailView.as_view(), name='detail_data_item'),
    path('settings/data-item-delete/<int:item_id>/<str:file_format_id>/<str:data_item_type_name>/',
         DataItemDeleteView.as_view(), name='delete_data_item'),

    # Rule settings URLs
    path('settings/rule-settings/', RuleSettingsView.as_view(), name='rule_settings'),
    path('settings/rule-detail/<int:rule_id>/<str:file_format_id>/<str:from_to_type>/',
         RuleDetailView.as_view(), name='detail_rule'),
    path('settings/rule-create/', RuleCreateView.as_view(), name='create_rule'),
    path('settings/rule-edit/<int:rule_id>/', RuleEditView.as_view(), name='edit_rule'),
    path('settings/rule-delete/<int:rule_id>/', RuleDeleteView.as_view(), name='delete_rule'),
    path('settings/get-items/', GetItemsView.as_view(), name='get_items'),

    # path('rule-settings/add-fixed-data/', AddFixedDataView.as_view(), name='add_fixed_data'),
    # path('rule-settings/delete-fixed-data/', DeleteFixedDataView.as_view(), name='delete_fixed_data'),
    # path('rule-settings/delete-rule/', DeleteRuleView.as_view(), name='delete_rule'),
    # path('rule-settings/save-header-settings/', SaveHeaderSettingsView.as_view(), name='save_header_settings'),
]