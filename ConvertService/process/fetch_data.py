import csv
from functools import lru_cache
import json
from accounts.models import Account
from .data_type import HeaderType, DisplayType, DownloadType
from configs.models import ConvertDataValue
from home.models import DataConversionInfo, DataFormat, DetailedInfo, DataItemType, FileFormat
from .redis import redis_client
import logging

logger = logging.getLogger(__name__)


class HeaderFetcher:
    @staticmethod
    def get_headers(user: Account, type_name: str, display: any, get_edit_header=False, data_format_id=None):
        """
        Fetch headers based on type_name, display flag and optionally data_format_id.
        """

        if type_name not in [HeaderType.INPUT.value, HeaderType.DISPLAY.value, HeaderType.AGENCY_OUTPUT.value, HeaderType.SYSTEM_OUTPUT.value]:
            logger.error(f"Invalid type_name: {type_name}")
            return []

        if display not in [DisplayType.SHOW.value, DisplayType.HIDDEN.value, DisplayType.ALL.value]:
            logger.error(f"Invalid display flag: {display}")
            return []

        try:
            tenant_id = user.tenant.id if user.tenant else 1

            data_format = None
            if data_format_id:
                try:
                    data_format = DataFormat.objects.get(
                        tenant_id=tenant_id,
                        data_format_id=data_format_id
                    )
                except DataFormat.DoesNotExist:
                    logger.warning(f"Data format {data_format_id} not found for tenant {tenant_id}, using default.")

            query_filter = {
                'data_item__tenant_id': tenant_id,
                'type_name': type_name,
            }

            if display is not None:
                query_filter['display'] = display

            if data_format:
                query_filter['data_item__data_format'] = data_format

            data_item_types = DataItemType.objects.filter(**query_filter).select_related('data_item')

            if get_edit_header:
                headers = [
                    {
                        'header_name': item.data_item.data_item_name,
                        'format_value': item.format_value,
                        'edit_value': item.edit_value,
                        'index_value': item.index_value,
                        'display': item.display,
                    } for item in data_item_types
                ]

                sorted_headers = sorted(
                    headers,
                    key=lambda x: (x['index_value'] is None, x['index_value'])
                )

                return sorted_headers
            else:
                data_items = [
                    {
                        'header_name': item.data_item.data_item_name,
                        'index_value': item.index_value,
                        'edit_value': item.edit_value,
                        'format_value': item.format_value,
                        'display':item.display,
                    }
                    for item in data_item_types
                ]

                sorted_headers = sorted(
                    data_items,
                    key=lambda x: (x['index_value'] is None, x['index_value'])
                )

                headers = [item['header_name'] for item in sorted_headers]
                return headers

        except Exception as e:
            logger.error(f"Error fetching headers: {e}")
            return []


class FileFormatFetcher:
    CONTENT_TYPE_MAP = {
        'text/csv': 'CSV_C_UTF-8',
        'application/csv': 'CSV_C_UTF-8',
        'text/plain': 'CSV_C_UTF-8',

        # Excel formats (new and old)
        'application/vnd.ms-excel': 'EXCEL',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'EXCEL',
        'application/excel': 'EXCEL',
        'application/x-excel': 'EXCEL',
        'application/x-msexcel': 'EXCEL',
        'application/vnd.ms-office': 'EXCEL',
        'application/msexcel': 'EXCEL',

        # JSON format
        'application/json': 'JSON',
        'text/json': 'JSON',

        # XML format
        'application/xml': 'XML',
        'text/xml': 'XML',
    }

    EXTENSION_MAP = {
        '.csv': 'CSV_C_UTF-8',
        '.tsv': 'CSV_T_UTF-8',
        '.xlsx': 'EXCEL',
        '.xls': 'EXCEL',
        '.json': 'JSON',
        '.xml': 'XML',
    }

    CACHE_TIMEOUT = 3600

    FORMAT_TO_DATA_FORMAT = {
        'CSV_C_SJIS': 'DF_003',
        'CSV_C_UTF-8': 'DF_003',
        'CSV_T_SJIS': 'DF_003',
        'CSV_T_UTF-8': 'DF_003',
        'XML': 'DF_002',
        'JSON': 'DF_002',
        'EXCEL': 'DF_004',
    }

    @staticmethod
    def get_data_format_id_for_file_format(file_format_id):
        return FileFormatFetcher.FORMAT_TO_DATA_FORMAT.get(file_format_id, 'DF_003')

    @staticmethod
    def get_allowed_formats_for_tenant(session_id, tenant_id):
        client = redis_client.get_client()
        cache_key = f'tenant:{tenant_id}:allowed_formats'

        first_extension = client.get(f'{session_id}-file-format')
        if first_extension:
            first_extension = first_extension.decode('utf-8')
            return [first_extension]

        cached_formats = client.get(cache_key)
        if cached_formats:
            return json.loads(cached_formats.decode('utf-8'))

        try:
            formats = DataFormat.objects.filter(
                tenant_id=tenant_id
            ).values_list(
                'file_format__file_format_id', flat=True
            ).distinct()

            allowed_formats = list(formats)

            if not allowed_formats:
                allowed_formats = []

            client.set(cache_key, json.dumps(allowed_formats), ex=FileFormatFetcher.CACHE_TIMEOUT)

            return allowed_formats
        except Exception as e:
            logger.error(f"Error fetching allowed file formats for tenant {tenant_id}: {e}")
            return []

    @staticmethod
    def is_valid_file_type(content_type, file_extension, allowed_formats=None):
        """
        Validate if the file type is allowed for this tenant
        """
        if not allowed_formats:
            allowed_formats = ['CSV_C_SJIS', 'CSV_C_UTF-8', 'CSV_T_SJIS', 'CSV_T_UTF-8', 'XML', 'JSON', 'EXCEL']

        format_by_content = FileFormatFetcher.CONTENT_TYPE_MAP.get(content_type)
        if format_by_content and format_by_content in allowed_formats:
            return True

        format_by_extension = FileFormatFetcher.EXTENSION_MAP.get(file_extension.lower())
        if format_by_extension and format_by_extension in allowed_formats:
            return True

        return False

    @staticmethod
    def get_file_format_for_content_type(content_type, file_extension):
        format_id = FileFormatFetcher.CONTENT_TYPE_MAP.get(content_type)
        if not format_id:
            format_id = FileFormatFetcher.EXTENSION_MAP.get(file_extension.lower())

        return format_id or 'CSV_C_SJIS'

    @staticmethod
    def get_file_format_id(user: Account, before=True, use_cache=True):
        """
        Get file format ID from Redis cache or database
        """
        try:
            tenant_id = user.tenant.id if user.tenant else 1
            session_key = getattr(user, 'session', {}).get('session_key', '')

            if session_key and use_cache:
                client = redis_client.get_client()
                cache_key = f'{session_key}-file-format-{"before" if before else "after"}'

                cached_format = client.get(cache_key)
                if cached_format:
                    return cached_format.decode('utf-8')

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

            if session_key and use_cache:
                client = redis_client.get_client()
                cache_key = f'{session_key}-file-format-{"before" if before else "after"}'
                client.set(cache_key, file_format, ex=FileFormatFetcher.CACHE_TIMEOUT)

            return file_format

        except Exception as e:
            logger.error(f"Error fetching file format ID: {e}")
            return None

    @staticmethod
    def get_output_file_format_id(user: Account, download_type, data_format_id):
        try:
            tenant_id = user.tenant.id if user.tenant else 1

            if not data_format_id:
                raise ValueError(f"No output data_format found for {download_type} download type")

            data_format_obj = DataFormat.objects.filter(data_format_id=data_format_id).first()
            if not data_format_obj:
                raise ValueError(f"Data format with ID {data_format_id} not found")

            conversion_info = DataConversionInfo.objects.filter(
                data_format_before_id=data_format_obj.id,
                tenant_id=tenant_id
            ).first()

            if not conversion_info:
                raise ValueError(f"No conversion info found for data format {data_format_id}")

            if download_type == DownloadType.SYSTEM.value:
                data_format_after = conversion_info.data_format_system_after
            else:
                data_format_after = conversion_info.data_format_agency_after

            if not data_format_after:
                raise ValueError(f"No output data format found for {download_type}")

            file_format_id = data_format_after.file_format.file_format_id

            if not file_format_id:
                raise ValueError(f"No file format found for the specified output data format")

            return file_format_id

        except Exception as e:
            logger.error(f"Error fetching output file format ID: {e}")
            return 'CSV_C_SJIS'

    @staticmethod
    def clear_format_cache():
        """
        Clear all file format cache entries
        """
        client = redis_client.get_client()
        keys = client.keys('*-file-format-*')
        keys.extend(client.keys('tenant:*:allowed_formats'))

        if keys:
            client.delete(*keys)
            logger.info(f"Cleared {len(keys)} file format cache entries")


class RuleFetcher:
    @staticmethod
    def get_rules(user: Account, before_type: str, after_type: str, data_format_id=None):
        try:
            tenant_id = user.tenant.id if user.tenant else 1

            data_convert = DataConversionInfo.objects.filter(
                tenant_id=tenant_id, data_format_before__data_format_id=data_format_id
            ).first()

            if not data_convert:
                raise ValueError("No data conversion found for this tenant.")

            filter_params = {
                'tenant_id': tenant_id,
                'data_convert': data_convert,
                'data_item_type_before__type_name': before_type,
                'data_item_type_after__type_name': after_type
            }

            detailed_infos = DetailedInfo.objects.filter(**filter_params).select_related(
                'data_item_type_before',
                'data_item_type_after',
                'convert_rule'
            )

            results = [
                {
                    'convert_rule_id': detail.convert_rule.convert_rule_id,
                    'index_before': detail.data_item_type_before.index_value,
                    'index_after': detail.data_item_type_after.index_value
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


class RuleFixedID:
    CR_GROUP_NO = "CR_GROUP_NO"
    CR_TIME_CODE1 = "CR_TIME_CODE1"
    CR_TIME_CODE2 = "CR_TIME_CODE2"
    CR_CAUSE_CODE1 = "CR_CAUSE_CODE1"
    CR_TIME_START = "CR_TIME_START"
    CR_TIME_END = "CR_TIME_END"

    @classmethod
    def get_data(cls):
        return {
            attr: getattr(cls, attr) for attr in dir(cls)
            if not attr.startswith('__') and not callable(getattr(cls, attr))
               and attr.isupper()
        }

    @classmethod
    def get_values(cls):
        return [
            getattr(cls, attr) for attr in dir(cls)
            if not attr.startswith('__') and not callable(getattr(cls, attr))
               and attr.isupper()
        ]


class FixedValueFetcher:
    @staticmethod
    @lru_cache(maxsize=128)
    def _get_mapping_for_rule(tenant_id, rule_fixed_id):
        try:
            query_filter = {
                'tenant_id': tenant_id,
                'convert_rule__convert_rule_id': rule_fixed_id
            }

            fixed_values = ConvertDataValue.objects.filter(**query_filter).values_list("data_value_before", "data_value_after")

            return {f"{before}": after for before, after in fixed_values}

        except Exception as e:
            logger.error(f"Error fetching fixed values for rule {rule_fixed_id}: {e}")
            return {}

    @classmethod
    def get_value_mapping(cls, tenant_id, rule_fixed_id, before_value=None):

        mapping = cls._get_mapping_for_rule(tenant_id, rule_fixed_id)

        if before_value is not None:
            return mapping.get(f"{before_value}", '')
        return mapping

    @classmethod
    def clear_cache(cls):
        cls._get_mapping_for_rule.cache_clear()