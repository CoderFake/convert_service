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
    GetItemsView,
    FixedDataListView,
    FixedDataDetailView,
    FixedDataBatchSaveView,
    FixedDataDeleteView,
    FixedRuleCreateView,
    FixedRuleUpdateView,
    FixedDataValuesView
)

urlpatterns = [
    path('settings/data-items/', DataItemListView.as_view(), name='data_items'),
    path('settings/data-item-create/', DataItemCreateView.as_view(), name='create_data_item'),
    path('settings/data-item-edit/<int:item_id>/', DataItemEditView.as_view(), name='edit_data_item'),
    path('settings/data-item-detail/<int:item_id>/<str:file_format_id>/<str:data_item_type_name>/',
         DataItemDetailView.as_view(), name='detail_data_item'),
    path('settings/data-item-delete/<int:item_id>/<str:file_format_id>/<str:data_item_type_name>/',
         DataItemDeleteView.as_view(), name='delete_data_item'),

    path('settings/rule-settings/', RuleSettingsView.as_view(), name='rule_settings'),
    path('settings/rule-detail/<int:rule_id>/<str:file_format_id>/<str:from_to_type>/',
         RuleDetailView.as_view(), name='detail_rule'),
    path('settings/rule-create/', RuleCreateView.as_view(), name='create_rule'),
    path('settings/rule-edit/<int:rule_id>/', RuleEditView.as_view(), name='edit_rule'),
    path('settings/rule-delete/<int:rule_id>/', RuleDeleteView.as_view(), name='delete_rule'),
    path('settings/get-items/', GetItemsView.as_view(), name='get_items'),

    path('settings/fixed-data/', FixedDataListView.as_view(), name='fixed_data'),
    path('settings/fixed-data-detail/<int:rule_id>/', FixedDataDetailView.as_view(), name='detail_fixed_data'),
    path('settings/fixed-data-batch-save/', FixedDataBatchSaveView.as_view(), name='batch_save_fixed_data'),
    path('settings/fixed-data-delete/<int:item_id>/', FixedDataDeleteView.as_view(), name='delete_fixed_data'),
    path('settings/fixed-data-delete-rule/<int:rule_id>/', FixedDataDeleteView.as_view(),
         name='delete_rule_fixed_data'),

    path('settings/fixed-rule-create/', FixedRuleCreateView.as_view(), name='create_fixed_rule'),
    path('settings/fixed-rule-update/<int:rule_id>/', FixedRuleUpdateView.as_view(), name='update_fixed_rule'),

    path('settings/fixed-data-values/<int:rule_id>/', FixedDataValuesView.as_view(), name='fixed_data_values'),
]