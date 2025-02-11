import base64
import csv
import io
import os
import logging
import threading
import zipfile
from django.utils import timezone
from .utils import (
    DataFormatter,
    FileProcessor,
    FileFormatMapper,
)
from .redis import redis_client
from concurrent.futures import ThreadPoolExecutor, as_completed
from celery import shared_task
from pathlib import Path
import json

logger = logging.getLogger(__name__)


@shared_task
def process_multiple_files_task(session_id, headers, file_format=None, mode='dict'):
    try:
        client = redis_client.get_client()
        redis_client.delete_key_batch(f'{session_id}-processed:*')

        keys = client.keys(f'{session_id}-file:*')
        if not keys:
            logger.warning("No files to process.")
            return {"status": "error", "message": "No files to process."}

        output_results = []

        def process_and_convert(file_path, key, file_index):
            try:
                file_path = Path(file_path)
                if mode == 'csv':
                    output_csv_path = file_path.with_suffix('.csv')
                    FileProcessor.process_file(file_path, headers, mode, file_format)
                    client.delete(key)
                    return {'type': 'csv', 'result': str(output_csv_path)}
                elif mode == 'dict':
                    result_dict = FileProcessor.process_file(file_path, headers, mode, file_format)

                    redis_key = f"{session_id}-processed:{file_index}"
                    client.set(redis_key, json.dumps(result_dict), ex=3600)

                    client.delete(key)
                    return {'type': 'dict', 'result': f"{len(result_dict)} rows processed."}
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
                return None

        max_workers = os.cpu_count() or 1
        logger.info(f"Processing files with {max_workers} workers.")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_and_convert, client.get(key).decode('utf-8'), key, file_index): key
                for file_index, key in enumerate(keys, start=1)
            }
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        output_results.append(result)
                except Exception as e:
                    logger.error(f"Error processing future: {e}")

        logger.info("All files processed successfully.")
        return {"status": "success", "results": output_results}

    except Exception as e:
        logger.error(f"Error in 'process_multiple_files_task': {e}")
        return {"status": "error", "message": "An error occurred while processing files."}


@shared_task
def process_and_format_file(
    session_id,
    fixed_values,
    rules,
    before_headers,
    after_headers,
    tenant_id,
    type_keys="processed:*"
):
    try:
        logger.info("Task 'process_and_format_file' started.")
        client = redis_client.get_client()

        keys = redis_client.scan_keys(f"{session_id}-{type_keys}")
        if not keys:
            logger.warning("No data found in Redis for processing.")
            return "処理するデータが見つかりません。"

        logger.info(f"Found {len(keys)} keys for processing.")
        max_workers = os.cpu_count() or 1
        logger.info(f"Using {max_workers} workers for processing.")

        batch_size = 500
        type_key = "output" if type_keys == "formatted:*" else "formatted"

        def process_batch(batch_keys):
            for key in batch_keys:
                try:
                    raw_data = client.get(key)
                    if not raw_data:
                        logger.warning(f"No valid data found for key {key}. Skipping...")
                        continue

                    data_dict = json.loads(raw_data.decode('utf-8'))

                    if isinstance(data_dict, list):
                        formatted_data = []
                        for idx, row in enumerate(data_dict):
                            formatted_row = DataFormatter.format_data_with_rules(
                                row,
                                fixed_values,
                                rules,
                                before_headers,
                                after_headers,
                                tenant_id
                            )
                            formatted_data.append(formatted_row)
                    else:
                        formatted_data = []
                        for row_key, row in data_dict.items():
                            formatted_row = DataFormatter.format_data_with_rules(
                                row,
                                fixed_values,
                                rules,
                                before_headers,
                                after_headers,
                                tenant_id
                            )
                            formatted_data.append(formatted_row)

                    formatted_key = f"{session_id}-{type_key}:{key.decode('utf-8').split(':')[1]}"
                    client.set(formatted_key, json.dumps(formatted_data), ex=3600)

                except Exception as e:
                    logger.error(f"Error processing key {key}: {e}")

            if type_key == "output":
                redis_client.delete_key_batch(batch_keys)

        batches = [keys[i:i + batch_size] for i in range(0, len(keys), batch_size)]

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_batch, batch): batch for batch in batches}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error in batch processing: {e}")

        logger.info("All keys processed successfully.")
        return "データは正常に処理され、保存されました。"

    except Exception as e:
        logger.error(f"Error in 'process_and_format_file' task: {e}")
        return "データフォーマット処理中にエラーが発生しました。"


@shared_task
def generate_zip_task(zip_key, headers, file_format_id):
    try:
        client = redis_client.get_client()
        keys = client.keys(zip_key)

        if not keys:
            logger.warning("No formatted data found for ZIP generation.")
            return None

        zip_buffer = io.BytesIO()

        format_details = FileFormatMapper.get_format_details(file_format_id)
        if not format_details:
            logger.error(f"Invalid file_format_id: {file_format_id}")
            return None

        delimiter = format_details['delimiter']
        encoding = format_details['encoding']

        def process_key(key):
            try:
                data = client.get(key)
                if not data:
                    return None, None

                formatted_data = json.loads(data)
                csv_buffer = io.StringIO()
                csv_writer = csv.writer(csv_buffer, delimiter=delimiter)

                csv_writer.writerow(headers)

                if isinstance(formatted_data, list):
                    for row in formatted_data:
                        if isinstance(row, dict):
                            csv_writer.writerow(row.values())
                        elif isinstance(row, list):
                            csv_writer.writerow(row)
                        else:
                            logger.warning(f"Invalid row format: {row}")

                client.delete(key)

                file_name = f"{timezone.now().strftime('%Y%m%d')}_output.csv"
                return file_name, csv_buffer.getvalue().encode(encoding)
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
        client.set(zip_key_name, zip_buffer.getvalue(), ex=3600)
        logger.info(f"ZIP file successfully created and saved to Redis with key {zip_key_name}.")
        return zip_key_name
    except Exception as e:
        logger.error(f"Error generating ZIP file: {e}")
        return None


@shared_task
def generate_csv_task(csv_key_pattern, headers, file_format_id):

    try:
        client = redis_client.get_client()
        keys = list(redis_client.scan_keys(csv_key_pattern))

        if not keys:
            logger.warning("No formatted data found for CSV generation.")
            return None

        format_details = FileFormatMapper.get_format_details(file_format_id)
        if not format_details:
            logger.error(f"Invalid file_format_id: {file_format_id}")
            return None

        delimiter = format_details['delimiter']
        encoding = format_details['encoding']

        csv_buffer = io.StringIO()
        csv_writer = csv.writer(csv_buffer, delimiter=delimiter)
        csv_writer.writerow(headers)

        buffer_lock = threading.Lock()

        max_workers = os.cpu_count() or 1

        def process_rows(key):
            try:
                data = client.get(key)
                if data:
                    formatted_data = json.loads(data)
                    client.delete(key)
                    return formatted_data
            except Exception as e:
                logger.error(f"Error processing key {key}: {e}")
                return []

        def write_row(row):
            try:
                if isinstance(row, dict):
                    return list(row.values())
                elif isinstance(row, list):
                    return row
                else:
                    logger.warning(f"Invalid row format: {row}")
                    return None
            except Exception as e:
                logger.error(f"Error preparing row for CSV: {e}")
                return None

        all_rows = []
        for key in keys:
            all_rows.extend(process_rows(key))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_row = {executor.submit(write_row, row): row for row in all_rows}

            for future in as_completed(future_to_row):
                try:
                    processed_row = future.result()
                    if processed_row is not None:
                        with buffer_lock:
                            csv_writer.writerow(processed_row)
                except Exception as e:
                    logger.error(f"Error writing row to CSV: {e}")

        csv_key_name = f"csv:{base64.urlsafe_b64encode(os.urandom(6)).decode('utf-8')}"
        client.set(csv_key_name, csv_buffer.getvalue().encode(encoding), ex=3600)
        return csv_key_name

    except Exception as e:
        logger.error(f"Critical error generating CSV file: {e}")
        return None