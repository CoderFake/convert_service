import base64
import csv
import io
import os
import logging
import threading
import zipfile
from django.utils import timezone
from process.utils import DataFormatter, get_redis_client, FileProcessor, FileFormatMapper, delete_all_keys
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

logger = logging.getLogger(__name__)

from celery import shared_task
from pathlib import Path

@shared_task
def process_multiple_files_task(session_id, headers, file_format=None, mode='dict'):

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
                FileProcessor.process_file(file_path, headers, mode, file_format)
                redis_client.delete(key)
                return {'type': 'csv', 'result': str(output_csv_path)}
            elif mode == 'dict':
                result_dict = FileProcessor.process_file(file_path, headers, mode, file_format)
                redis_key = f"{session_id}-processed:{base64.urlsafe_b64encode(os.urandom(6)).decode('utf-8')}"
                redis_client.set(redis_key, json.dumps(result_dict), ex=3600)
                redis_client.delete(key)
                return {'type': 'dict', 'result': redis_key}
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            return None

    max_workers = os.cpu_count() or 1
    logger.info(f"Processing files with {max_workers} workers.")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_and_convert, redis_client.get(key).decode('utf-8'), key): key for key in
                   keys}
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    output_results.append(result)
            except Exception as e:
                logger.error(f"Error processing future: {e}")

    logger.info("All files processed successfully.")
    return {"status": "success", "results": output_results}


@shared_task
def process_and_format_file(session_id, fixed_values, rules, before_headers, after_headers, tenant_id, keys="processed:*"):
    try:
        logger.info("Task 'process_and_format_file' started.")
        redis_client = get_redis_client()

        type_key = "formatted"
        if keys == "processed:*":
            formatted_keys = redis_client.keys(f'{session_id}-formatted:*')
            delete_key_batch(redis_client, formatted_keys)

        else:
            output_keys = redis_client.keys(f'{session_id}-output:*')
            delete_key_batch(redis_client, output_keys)
            type_key = "output"

        keys = redis_client.keys(f"{session_id}-{keys}")

        if type_key == "output":
            keys = sorted(keys, key=lambda x: int(x.decode("utf-8").split(":")[1]))

        if not keys:
            logger.warning("No data found in Redis for processing.")
            return "処理するデータが見つかりません。"

        global_row_index = 0
        max_workers = os.cpu_count() or 1
        logger.info(f"Using {max_workers} workers for processing.")

        for key in keys:
            raw_data = redis_client.get(key)
            if not raw_data:
                logger.warning(f"No valid data found for key {key}. Skipping...")
                continue

            data = json.loads(raw_data.decode('utf-8'))

            def process_batch(rows, start_index):
                formatted_rows = []
                for row_index, row in enumerate(rows):
                    try:
                        formatted_row = DataFormatter.format_data_with_rules(
                            row,
                            fixed_values,
                            rules,
                            before_headers,
                            after_headers,
                            tenant_id
                        )
                        formatted_rows.append((start_index + row_index, formatted_row))
                    except Exception as e:
                        logger.error(f"Error processing row {start_index + row_index}: {e}")
                return formatted_rows

            batch_size = 100
            batches = [data[i:i + batch_size] for i in range(0, len(data), batch_size)]
            if type_key == "output":
                batches = [batches]
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                for batch_index, batch in enumerate(batches):
                    start_index = global_row_index + batch_index * batch_size
                    futures = executor.submit(process_batch, batch, start_index)
                    for row_index, formatted_row in futures.result():
                        if formatted_row is not None:
                            formatted_key = f"{session_id}-{type_key}:{row_index}"
                            redis_client.set(formatted_key, json.dumps(formatted_row), ex=3600)

            global_row_index += len(data)

        if type_key == "output":
            redis_client.delete(f'{session_id}-formatted:*')

        return "データは正常に処理され、保存されました。"

    except Exception as e:
        logger.error(f"Error in 'process_and_format_file' task: {e}")
        return "データフォーマット処理中にエラーが発生しました。"


def delete_key_batch(redis_client, keys):
    try:
        pipeline = redis_client.pipeline()
        for key in keys:
            pipeline.delete(key)
        pipeline.execute()
        logger.info(f"Deleted {len(keys)} keys from Redis.")
    except Exception as e:
        logger.error(f"Error deleting keys: {e}")

@shared_task
def generate_zip_task(zip_key, headers, file_format_id):
    try:
        redis_client = get_redis_client()
        keys = redis_client.keys(zip_key)

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
                data = redis_client.get(key)
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

                redis_client.delete(key)

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
        redis_client.set(zip_key_name, zip_buffer.getvalue(), ex=3600)
        logger.info(f"ZIP file successfully created and saved to Redis with key {zip_key_name}.")
        return zip_key_name
    except Exception as e:
        logger.error(f"Error generating ZIP file: {e}")
        return None


@shared_task
def generate_csv_task(csv_key, headers, file_format_id):
    lock = threading.Lock()
    try:
        redis_client = get_redis_client()
        keys = redis_client.keys(csv_key)
        format_keys = sorted(keys, key=lambda x: int(x.decode("utf-8").split(":")[1]))

        if not format_keys:
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


        def process_key(key):
            try:
                data = redis_client.get(key)
                if not data:
                    return None
                formatted_data = json.loads(data)
                redis_client.delete(key)
                return formatted_data
            except Exception as e:
                logger.error(f"Error processing key {key}: {e}")
                return None

        max_workers = os.cpu_count() or 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_key, key): key for key in format_keys}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        with lock:
                            try:
                                if isinstance(result, dict):
                                    csv_writer.writerow(result.values())
                                elif isinstance(result, list):
                                    csv_writer.writerow(result)
                                else:
                                    logger.warning(f"Invalid row format: {result}")
                            except Exception as e:
                                logger.error(f"Error writing row to CSV: {e}")
                                if lock.locked():
                                    lock.release()
                                raise
                except Exception as e:
                    logger.error(f"Error occurred in future result: {e}")
                    continue

        csv_key_name = f"csv:{base64.urlsafe_b64encode(os.urandom(6)).decode('utf-8')}"
        redis_client.set(csv_key_name, csv_buffer.getvalue().encode(encoding), ex=3600)
        return csv_key_name

    except Exception as e:
        logger.error(f"Critical error generating CSV file: {e}")
        if lock.locked():
            lock.release()
        return None

