import base64
import csv
import io
import os
import logging
import zipfile
from django.utils import timezone

from home.models import DataConversionInfo
from home.dataclasses import PatientRecord
from process.utils import DataFormatter, get_redis_client, FileProcessor
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

logger = logging.getLogger(__name__)

from celery import shared_task
from pathlib import Path

@shared_task
def process_multiple_files_task(mode='dict'):

    redis_client = get_redis_client()
    processed_keys = redis_client.keys('processed:*')

    for key in processed_keys:
        redis_client.delete(key)

    keys = redis_client.keys('file:*')
    if not keys:
        logger.warning("No files to process.")
        return {"status": "error", "message": "No files to process."}

    output_results = []

    def process_and_convert(file_path, key):
        try:
            file_path = Path(file_path)
            if mode == 'csv':
                output_csv_path = file_path.with_suffix('.csv')
                FileProcessor.process_file(file_path, output_csv_path, mode='csv')
                redis_client.delete(key)
                return {'type': 'csv', 'result': str(output_csv_path)}
            elif mode == 'dict':
                result_dict = FileProcessor.process_file(file_path, mode='dict')
                redis_key = f"processed:{base64.urlsafe_b64encode(os.urandom(6)).decode('utf-8')}"
                redis_client.set(redis_key, json.dumps(result_dict), ex=3600)
                redis_client.delete(key)
                return {'type': 'dict', 'result': redis_key}
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            return None

    max_workers = os.cpu_count() or 1
    logger.info(f"Processing files with {max_workers} workers.")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_and_convert, redis_client.get(key).decode('utf-8'), key): key
            for key in keys
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                output_results.append(result)

    logger.info("All files processed successfully.")
    return {"status": "success", "results": output_results}


@shared_task
def process_and_format_file(data_convert_id):
    """
    Process and format file based on conversion rules.
    """
    try:
        logger.info("Task 'process_and_format_file' started.")
        redis_client = get_redis_client()

        formatted_keys = redis_client.keys('formatted:*')
        for key in formatted_keys:
            redis_client.delete(key)
        logger.info(f"Deleted {len(formatted_keys)} formatted keys from Redis.")

        keys = redis_client.keys('processed:*')
        if not keys:
            logger.warning("No data found in Redis for processing.")
            return "処理するデータが見つかりません。"

        conversion_info = DataConversionInfo.objects.prefetch_related(
            'detailedinfo_set__data_item_id_before',
            'detailedinfo_set__data_item_id_after',
            'detailedinfo_set__convert_rule'
        ).get(data_convert_id=data_convert_id)

        detailed_info = conversion_info.detailedinfo_set.all()

        rules = [[detail.convert_rule.convert_rule_id, detail.data_item_id_before.data_item_name,
                  detail.data_item_id_after.data_item_name] for detail in detailed_info]
        headers = list(PatientRecord.COLUMN_NAMES.values())

        def process_single_key(key):
            try:
                raw_data = redis_client.get(key)
                if raw_data:
                    data = json.loads(raw_data.decode('utf-8'))
                    formatted_data = DataFormatter.format_data_with_rules(data, rules, headers)
                    formatted_key = f"formatted:{base64.urlsafe_b64encode(os.urandom(6)).decode('utf-8')}"
                    redis_client.set(formatted_key, json.dumps(formatted_data), ex=3600)
                    logger.info(f"Saved formatted data to Redis: {formatted_key}")
            except Exception as e:
                logger.error(f"Error processing key {key}: {e}")

        max_workers = os.cpu_count() or 1
        logger.info(f"Processing files with {max_workers} workers.")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_single_key, key) for key in keys]
            for future in as_completed(futures):
                future.result()

        logger.info("All data has been successfully processed and stored.")
        return "データは正常に処理され、保存されました。"

    except DataConversionInfo.DoesNotExist:
        logger.error(f"Conversion settings for ID '{data_convert_id}' not found.")
        return "指定されたデータ変換IDの設定が見つかりませんでした"
    except Exception as e:
        logger.error(f"Error in 'process_and_format_file' task: {e}")
        return "データフォーマット処理中にエラーが発生しました。"


@shared_task
def generate_zip_task(zip_key, headers):
    try:
        redis_client = get_redis_client()
        keys = redis_client.keys(zip_key)

        if not keys:
            logger.warning("No formatted data found for ZIP generation.")
            return None

        zip_buffer = io.BytesIO()

        def process_key(key):
            try:
                data = redis_client.get(key)
                if not data:
                    return None, None

                formatted_data = json.loads(data)
                csv_buffer = io.StringIO()
                csv_writer = csv.writer(csv_buffer)
                csv_writer.writerow(headers)

                if isinstance(formatted_data, list):
                    for row in formatted_data:
                        if isinstance(row, dict):
                            csv_writer.writerow(row.values())
                        elif isinstance(row, list):
                            csv_writer.writerow(row)
                        else:
                            logger.warning(f"Invalid row format: {row}")

                redis_client.delete(key)

                file_name = f"{timezone.now().strftime('%Y%m%d')}_output.csv"
                return file_name, csv_buffer.getvalue()
            except Exception as e:
                logger.error(f"Error processing key {key}: {e}")
                return None, None


        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {executor.submit(process_key, key): key for key in keys}

                for future in as_completed(futures):
                    file_name, csv_content = future.result()
                    if file_name and csv_content:
                        zip_file.writestr(file_name, csv_content)
                        logger.info(f"Added file {file_name} to ZIP.")


        zip_key_name = f"zip:{base64.urlsafe_b64encode(os.urandom(6)).decode('utf-8')}"
        redis_client.set(zip_key_name, zip_buffer.getvalue(), ex=3600)
        logger.info(f"ZIP file successfully created and saved to Redis with key {zip_key_name}.")
        return zip_key_name
    except Exception as e:
        logger.error(f"Error generating ZIP file: {e}")
        return None
