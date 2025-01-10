import enum
from accounts.models import Account
from django.db.models import Q, F
from .models import DataConversionInfo, DataFormat, DetailedInfo, DataItemType
import logging

logger = logging.getLogger(__name__)


class HeaderType(enum.Enum):
    BEFORE = 'input'
    FORMAT = 'format'
    AFTER = 'output'


class DisplayType(enum.Enum):
    SHOW = True
    HIDDEN = False
    ALL = None


class HeaderFetcher:
    @staticmethod
    def get_headers(user: Account, type_name: str, display: any, edit=False):
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
            elif not edit:
                data_item_types = DataItemType.objects.filter(
                    data_item__tenant_id=tenant_id,
                    type_name=type_name,
                    display=display
                ).select_related('data_item')
            else:
                data_item_types = DataItemType.objects.filter(
                    data_item__tenant_id=tenant_id,
                    type_name=type_name,
                    display=display,
                    edit_value=True
                ).select_related('data_item')


            data_items = [
                {
                    'data_item_name': item.data_item.data_item_name,
                    'edit_value': item.edit_value,
                    'format_value': item.format_value,
                    'sort_index': item.index_value
                }
                for item in data_item_types
            ]

            sorted_headers = sorted(
                data_items,
                key=lambda x: (x['sort_index'] is None, x['sort_index'])
            )

            headers = [item['data_item_name'] for item in sorted_headers]
            #
            # if edit:
            #     headers = {
            #         {
            #             'header_name': item['data_item_name'],
            #             'edit_value': item['edit_value'],
            #             'format_value': item['format_value']
            #         } for item in sorted_headers
            #     }
            #
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

            data_convert_id = DataConversionInfo.objects.filter(
                tenant_id=tenant_id
            ).values_list('data_convert_id', flat=True).first()

            if not data_convert_id:
                raise ValueError("No data_convert_id found for this tenant.")

            detailed_infos = DetailedInfo.objects.filter(
                data_convert__data_convert_id=data_convert_id
            ).select_related('data_item_id_before', 'data_item_id_after', 'convert_rule')

            results = []
            for detail in detailed_infos:

                if before_type == DataItemType.TypeName.BEFORE:
                    before_item = detail.data_item_id_before
                elif before_type == DataItemType.TypeName.FORMAT:
                    before_item = detail.data_item_id_after
                else:
                    continue

                if after_type == DataItemType.TypeName.FORMAT:
                    after_item = detail.data_item_id_before
                elif after_type == DataItemType.TypeName.AFTER:
                    after_item = detail.data_item_id_after
                else:
                    continue

                after_item_type = DataItemType.objects.filter(
                    data_item__data_item_name=after_item,
                    type_name=after_type
                ).first()

                if not after_item_type:
                    logger.warning(f"No DataItemType found for {before_item} with type {before_type}")
                    continue

                results.append({
                    'header_before_name': before_item.data_item_name,
                    'header_after_name': after_item.data_item_name,
                    'convert_rule_id': detail.convert_rule.convert_rule_id,
                    'sort_index': after_item_type.index_value
                })

            sorted_results = sorted(
                results,
                key=lambda x: (x['sort_index'] is None, x['sort_index'])
            )

            return [[item['convert_rule_id'], item['sort_index']] for item in sorted_results]


        except Exception as e:
            logger.error(f"Error fetching conversion rules: {e}")
            return []
