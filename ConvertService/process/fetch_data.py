from accounts.models import Account
from .data_type import HeaderType, DisplayType
from configs.models import ConvertDataValue
from home.models import DataConversionInfo, DataFormat, DetailedInfo, DataItemType
import logging

logger = logging.getLogger(__name__)


class HeaderFetcher:
    @staticmethod
    def get_headers(user: Account, type_name: str, display: any, get_edit_header=False):
        """
        Fetch headers based on type_name and display flag.
        """

        if type_name not in [HeaderType.BEFORE.value, HeaderType.FORMAT.value, HeaderType.AFTER.value]:
            logger.error(f"Invalid type_name: {type_name}")
            return []

        if display not in [DisplayType.SHOW.value, DisplayType.HIDDEN.value, DisplayType.ALL.value]:
            logger.error(f"Invalid display flag: {display}")
            return []

        try:
            tenant_id = user.tenant.id if user.tenant else 1
            if display is None:
                data_item_types = DataItemType.objects.filter(
                    data_item__tenant_id=tenant_id,
                    type_name=type_name
                ).select_related('data_item')
            else:
                data_item_types = DataItemType.objects.filter(
                    data_item__tenant_id=tenant_id,
                    type_name=type_name,
                    display=display
                ).select_related('data_item')

            data_items = [
                {
                    'header_name': item.data_item.data_item_name,
                    'index_value': item.index_value,
                    'edit_value': item.edit_value,
                    'format_value': item.format_value
                }
                for item in data_item_types
            ]

            sorted_headers = sorted(
                data_items,
                key=lambda x: (x['index_value'] is None, x['index_value'])
            )

            headers = [item['header_name'] for item in sorted_headers]

            if get_edit_header:
                headers = [
                    {
                        'header_name': item.data_item.data_item_name,
                        'format_value': item.format_value,
                        'edit_value': item.edit_value,
                        'index_value': item.index_value
                    } for item in data_item_types
                ]
                sorted_headers = sorted(
                    headers,
                    key=lambda x: (x['index_value'] is None, x['index_value'])
                )

                return sorted_headers

            return headers

        except Exception as e:
            logger.error(f"Error fetching headers: {e}")
            return []


class FileFormatFetcher:

    @staticmethod
    def get_file_format_id(user: Account, before= True):
        try:
            tenant_id = user.tenant.id if user.tenant else 1

            data_format_column = 'data_format_before_id' if before else 'data_format_after_id'

            data_format_id = DataConversionInfo.objects.filter(
                tenant_id=tenant_id
            ).values_list(data_format_column, flat=True).first()

            if not data_format_id:
                raise ValueError(f"No {'before' if before else 'after'} data_format found for this tenant.")

            file_format = DataFormat.objects.filter(
                id=data_format_id, tenant_id=tenant_id
            ).values_list('file_format__file_format_id', flat=True).first()

            if not file_format:
                raise ValueError("No file format found for the specified data_format.")

            return file_format

        except Exception as e:
            logger.error(f"Error fetching file format ID: {e}")
            return None


class RuleFetcher:
    @staticmethod
    def get_rules(user: Account, before_type: str, after_type: str):
        try:
            tenant_id = user.tenant.id if user.tenant else 1

            data_convert = DataConversionInfo.objects.filter(
                tenant_id=tenant_id
            ).first()

            if not data_convert:
                raise ValueError("No data conversion found for this tenant.")

            detailed_infos = DetailedInfo.objects.filter(
                tenant_id=tenant_id,
                data_convert=data_convert,
                data_item_type_id_before__type_name=before_type,
                data_item_type_id_after__type_name=after_type
            ).select_related(
                'data_item_type_id_before',
                'data_item_type_id_after',
                'convert_rule'
            )

            results = [
                {
                    'convert_rule_id': detail.convert_rule.convert_rule_id,
                    'index_before': detail.data_item_type_id_before.index_value,
                    'index_after': detail.data_item_type_id_after.index_value
                }
                for detail in detailed_infos
            ]

            sorted_results = sorted(
                results,
                key=lambda x: (x['index_after'] is None, x['index_after'])
            )

            return [
                [item['convert_rule_id'], item['index_before'], item['index_after']]
                for item in sorted_results
            ]

        except Exception as e:
            logger.error(f"Error fetching conversion rules: {e}")
            return []


class FixedValueFetcher:

    @staticmethod
    def get_fixed_values(user: Account):
        try:
            tenant_id = user.tenant.id if user.tenant else 1
            fixed_values = ConvertDataValue.objects.filter(tenant_id=tenant_id).values(
                "data_value_before", "data_value_after"
            )

            return list(fixed_values)

        except Exception as e:
            logger.error(f"Error fetching fixed values: {e}")
            return []