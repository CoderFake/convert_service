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
    CharacterNormalizer,  
)
from .redis import redis_client
from concurrent.futures import ThreadPoolExecutor, as_completed
from celery import shared_task
from pathlib import Path
import json

logger = logging.getLogger(__name__)


@shared_task
def process_multiple_files_task(session_id, headers):

    try:
        client = redis_client.get_client()
        redis_client.delete_key_batch(client.keys(f'{session_id}-processed:*'))

        keys = client.keys(f'{session_id}-file:*')
        if not keys:
            logger.warning("No files to process.")
            return {"status": "error", "message": "No files to process."}

        output_results = []

        def process_and_convert(file_path, key, file_index):
            try:
                file_path = Path(file_path)
                result_dict = FileProcessor.process_file(file_path, headers)

                redis_key = f"{session_id}-processed:{file_index}"
                client.set(redis_key, json.dumps(result_dict), ex=3600)

                client.delete(key)
                return {'type': 'dict', 'result': f"{len(result_dict)} rows processed."}
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
                return {'type': 'error', 'result': str(e)}

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
        return {"status": "error", "message": f"An error occurred while processing files: {str(e)}"}


@shared_task
def process_and_format_file(
        session_id,
        rules,
        before_headers,
        after_headers,
        tenant_id,
        type_keys="processed:*",
        data_format_id=None
):
    try:
        logger.info("Task 'process_and_format_file' started.")
        client = redis_client.get_client()

        keys = redis_client.scan_keys(f"{session_id}-{type_keys}")
        if not keys:
            logger.warning("No data found in Redis for processing.")
            return "処理するデータが見つかりません。"

        logger.info(f"Found {len(keys)} keys for processing.")
        type_key = "output" if type_keys == "display:*" else "display"

        sorted_keys = sorted(keys, key=lambda k: int(k.decode('utf-8').split(':')[1])
        if k.decode('utf-8').split(':')[1].isdigit() else 0)

        row_index_counter = 0

        for key in sorted_keys:
            try:
                raw_data = client.get(key)
                if not raw_data:
                    logger.warning(f"No valid data found for key {key}. Skipping...")
                    continue

                data_dict = json.loads(raw_data.decode('utf-8'))

                if isinstance(data_dict, list):
                    display_data = []
                    for idx, row in enumerate(data_dict):
                        if isinstance(row, dict):
                            row['row_index'] = row_index_counter + idx

                        display_row = DataFormatter.format_data_with_rules(
                            row,
                            rules,
                            before_headers,
                            after_headers,
                            tenant_id
                        )

                        if isinstance(display_row, list) and len(display_row) > 0:
                            display_data.append(display_row)

                else:
                    display_data = []
                    for idx, (row_key, row) in enumerate(data_dict.items()):
                        if isinstance(row, dict):
                            row['row_index'] = row_index_counter + idx

                        display_row = DataFormatter.format_data_with_rules(
                            row,
                            rules,
                            before_headers,
                            after_headers,
                            tenant_id
                        )
                        display_data.append(display_row)

                display_key = f"{session_id}-{type_key}:{key.decode('utf-8').split(':')[1]}"
                client.set(display_key, json.dumps(display_data), ex=3600)

                row_index_counter += len(display_data)

            except Exception as e:
                logger.error(f"Error processing key {key}: {e}")

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
            logger.warning("No display data found for ZIP generation.")
            return None

        zip_buffer = io.BytesIO()

        format_details = FileFormatMapper.get_format_details(file_format_id)
        if not format_details:
            logger.error(f"Invalid file_format_id: {file_format_id}")
            return None

        delimiter = format_details['delimiter']
        encoding = format_details['encoding']

        sorted_keys = sorted(keys, key=lambda k: int(k.decode('utf-8').split(':')[1]) if k.decode('utf-8').split(':')[1].isdigit() else 0)
        all_data = []
        for key in sorted_keys:
            try:
                data = client.get(key)
                if data:
                    display_data = json.loads(data)
                    all_data.extend(display_data)
                client.delete(key)
            except Exception as e:
                logger.error(f"Error processing key {key}: {e}")

        csv_buffer = io.StringIO()
        csv_writer = csv.writer(csv_buffer, delimiter=delimiter)
        csv_writer.writerow(headers)

        for row in all_data:
            if isinstance(row, dict):
                csv_writer.writerow(row.values())
            elif isinstance(row, list):
                csv_writer.writerow(row)
            else:
                logger.warning(f"Invalid row format: {row}")

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            file_name = f"{timezone.now().strftime('%Y%m%d')}_output.csv"
            zip_file.writestr(file_name, csv_buffer.getvalue().encode(encoding))
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
    """
    Generate a CSV file from display data stored in Redis.

    Args:
        csv_key_pattern: Redis key pattern to find display data
        headers: List of column headers
        file_format_id: ID of the file format (encoding, delimiter)

    Returns:
        Redis key where the generated CSV is stored, or None on failure
    """
    try:
        client = redis_client.get_client()
        keys = list(redis_client.scan_keys(csv_key_pattern))

        if not keys:
            logger.warning("No display data found for CSV generation.")
            return None

        format_details = FileFormatMapper.get_format_details(file_format_id)
        if not format_details:
            logger.error(f"Invalid file_format_id: {file_format_id}")
            return None

        delimiter = format_details['delimiter']
        encoding = format_details['encoding']

        sorted_keys = sorted(keys, key=lambda k: int(k.decode('utf-8').split(':')[1])
        if k.decode('utf-8').split(':')[1].isdigit() else 0)

        csv_buffer = io.StringIO()
        csv_writer = csv.writer(csv_buffer, delimiter=delimiter)
        csv_writer.writerow(headers)

        all_rows = []
        for key in sorted_keys:
            try:
                data = client.get(key)
                if data:
                    display_data = json.loads(data)
                    all_rows.extend(display_data)
            except Exception as e:
                logger.error(f"Error processing key {key}: {e}")
                continue

        for row in all_rows:
            try:
                if isinstance(row, dict):
                    values = [CharacterNormalizer.safe_normalize(val) for val in row.values()]
                    csv_writer.writerow(values)
                elif isinstance(row, list):
                    values = [CharacterNormalizer.safe_normalize(val) for val in row]
                    csv_writer.writerow(values)
                else:
                    logger.warning(f"Invalid row format: {type(row)}. Skipping.")
            except Exception as e:
                logger.error(f"Error writing row to CSV: {e}")
                continue

        csv_key_name = f"csv:{base64.urlsafe_b64encode(os.urandom(6)).decode('utf-8')}"
        client.set(csv_key_name, csv_buffer.getvalue().encode(encoding, errors='ignore'), ex=3600)
        logger.info(f"CSV file created successfully with key {csv_key_name}")
        return csv_key_name

    except Exception as e:
        logger.error(f"Critical error generating CSV file: {e}")
        return None


@shared_task
def generate_excel_task(excel_key_pattern, headers, sheet_name):
    """
    Generate an Excel file from display data stored in Redis.

    Args:
        excel_key_pattern: Redis key pattern to find display data
        headers: List of column headers
        sheet_name: Name for the Excel sheet

    Returns:
        Redis key where the generated Excel file is stored, or None on failure
    """
    try:
        client = redis_client.get_client()
        keys = list(redis_client.scan_keys(excel_key_pattern))

        if not keys:
            logger.warning("No display data found for Excel generation.")
            return None

        import pandas as pd
        import io
        from openpyxl import Workbook
        from openpyxl.utils.dataframe import dataframe_to_rows

        wb = Workbook()
        ws = wb.active
        ws.title = sheet_name

        ws.append(headers)

        sorted_keys = sorted(keys, key=lambda k: int(k.decode('utf-8').split(':')[1])
        if k.decode('utf-8').split(':')[1].isdigit() else 0)

        all_rows = []
        for key in sorted_keys:
            try:
                data = client.get(key)
                if data:
                    display_data = json.loads(data)
                    all_rows.extend(display_data)
            except Exception as e:
                logger.error(f"Error processing key {key}: {e}")
                continue

        for row in all_rows:
            try:
                if isinstance(row, dict):
                    values = [CharacterNormalizer.safe_normalize(val) for val in row.values()]
                    ws.append(values)
                elif isinstance(row, list):
                    values = [CharacterNormalizer.safe_normalize(val) for val in row]
                    ws.append(values)
                else:
                    logger.warning(f"Invalid row format: {type(row)}. Skipping.")
            except Exception as e:
                logger.error(f"Error adding row to Excel: {e}")
                continue

        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if cell.value and len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2)
            ws.column_dimensions[column_letter].width = min(adjusted_width, 50)

        excel_buffer = io.BytesIO()
        wb.save(excel_buffer)
        excel_buffer.seek(0)

        excel_key_name = f"excel:{base64.urlsafe_b64encode(os.urandom(6)).decode('utf-8')}"
        client.set(excel_key_name, excel_buffer.getvalue(), ex=3600)

        logger.info(f"Excel file created successfully with key {excel_key_name}")
        return excel_key_name

    except Exception as e:
        logger.error(f"Error generating Excel file: {e}")
        return None
