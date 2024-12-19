from accounts.models import Account
from django.db.models import Q, F
from .models import DataItem, DataConversionInfo, DataFormat, DetailedInfo
import logging

logger = logging.getLogger(__name__)


class HeaderFetcher:
    @staticmethod
    def get_headers(user: Account, before=True):

        try:
            tenant_id = user.tenant.id if user.tenant else 1

            data_convert_id = DataConversionInfo.objects.filter(
                tenant_id=tenant_id
            ).values_list('data_convert_id', flat=True).first()

            if not data_convert_id:
                raise ValueError("No data_convert_id found for this tenant.")

            if before:
                detailed_infos = DetailedInfo.objects.filter(
                    data_convert__data_convert_id=data_convert_id
                ).select_related('data_item_id_before')
            else:
                detailed_infos = DetailedInfo.objects.filter(
                    data_convert__data_convert_id=data_convert_id
                ).select_related('data_item_id_after')

            data_items = []
            for detail in detailed_infos:
                if before:
                    data_item = detail.data_item_id_before
                else:
                    data_item = detail.data_item_id_after

                data_items.append({
                    'data_item_name': data_item.data_item_name,
                    'sort_index': data_item.data_item_index
                })

            sorted_headers = sorted(
                data_items,
                key=lambda x: (x['sort_index'] is None, x['sort_index'])
            )

            headers = [item['data_item_name'] for item in sorted_headers]
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
    def get_rules(user: Account, before=False):

        try:
            tenant_id = user.tenant.id if user.tenant else 1

            data_convert_id = DataConversionInfo.objects.filter(
                tenant_id=tenant_id
            ).values_list('data_convert_id', flat=True).first()

            if not data_convert_id:
                raise ValueError("No data_convert_id found for this tenant.")

            if before:
                detailed_infos = DetailedInfo.objects.filter(
                    data_convert__data_convert_id=data_convert_id
                ).select_related('data_item_id_before', 'convert_rule')
            else:
                detailed_infos = DetailedInfo.objects.filter(
                    data_convert__data_convert_id=data_convert_id
                ).select_related('data_item_id_after', 'convert_rule')

            rules = []
            for detail in detailed_infos:
                if before:
                    data_item = detail.data_item_id_before
                else:
                    data_item = detail.data_item_id_after

                rules.append({
                    'convert_rule': detail.convert_rule.convert_rule_id,
                    'sort_index': data_item.data_item_index
                })

            sorted_rules = sorted(
                rules,
                key=lambda x: (x['sort_index'] is None, x['sort_index'])
            )

            rule_ids = [item['convert_rule'] for item in sorted_rules]
            return rule_ids

        except Exception as e:
            logger.error(f"Error fetching conversion rules: {e}")
            return []
