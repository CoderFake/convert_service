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
        max_workers = os.cpu_count() or 1
        logger.info(f"Using {max_workers} workers for processing.")

        batch_size = 500
        type_key = "output" if type_keys == "formatted:*" else "formatted"
        
        # Sort keys to maintain original file order
        sorted_keys = sorted(keys, key=lambda k: int(k.decode('utf-8').split(':')[1]) if k.decode('utf-8').split(':')[1].isdigit() else 0)
        
        # Process files sequentially to maintain continuous row indexing
        row_index_counter = 0
        
        for key in sorted_keys:
            try:
                raw_data = client.get(key)
                if not raw_data:
                    logger.warning(f"No valid data found for key {key}. Skipping...")
                    continue

                data_dict = json.loads(raw_data.decode('utf-8'))

                if isinstance(data_dict, list):
                    formatted_data = []
                    for idx, row in enumerate(data_dict):
                        if isinstance(row, dict):
                            row['row_index'] = row_index_counter + idx
                        
                        formatted_row = DataFormatter.format_data_with_rules(
                            row,
                            rules,
                            before_headers,
                            after_headers,
                            tenant_id,
                            data_format_id
                        )
                        
                        if isinstance(formatted_row, list) and len(formatted_row) > 0:
                            formatted_data.append(formatted_row)
                else:
                    formatted_data = []
                    for idx, (row_key, row) in enumerate(data_dict.items()):
                        if isinstance(row, dict):
                            row['row_index'] = row_index_counter + idx
                            
                        formatted_row = DataFormatter.format_data_with_rules(
                            row,
                            rules,
                            before_headers,
                            after_headers,
                            tenant_id,
                            data_format_id
                        )
                        formatted_data.append(formatted_row)

                formatted_key = f"{session_id}-{type_key}:{key.decode('utf-8').split(':')[1]}"
                client.set(formatted_key, json.dumps(formatted_data), ex=3600)

                row_index_counter += len(formatted_data)
                
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
            logger.warning("No formatted data found for ZIP generation.")
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
                    formatted_data = json.loads(data)
                    all_data.extend(formatted_data)
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

        incompatible_chars = {
            # Circled numbers
            '\u2460': '(1)',  # ① -> (1)
            '\u2461': '(2)',  # ② -> (2)
            '\u2462': '(3)',  # ③ -> (3)
            '\u2463': '(4)',  # ④ -> (4)
            '\u2464': '(5)',  # ⑤ -> (5)
            '\u2465': '(6)',  # ⑥ -> (6)
            '\u2466': '(7)',  # ⑦ -> (7)
            '\u2467': '(8)',  # ⑧ -> (8)
            '\u2468': '(9)',  # ⑨ -> (9)
            '\u2469': '(10)',  # ⑩ -> (10)
            '\u246A': '(11)',  # ⑪ -> (11)
            '\u246B': '(12)',  # ⑫ -> (12)
            '\u246C': '(13)',  # ⑬ -> (13)
            '\u246D': '(14)',  # ⑭ -> (14)
            '\u246E': '(15)',  # ⑮ -> (15)
            '\u246F': '(16)',  # ⑯ -> (16)
            '\u2470': '(17)',  # ⑰ -> (17)
            '\u2471': '(18)',  # ⑱ -> (18)
            '\u2472': '(19)',  # ⑲ -> (19)
            '\u2473': '(20)',  # ⑳ -> (20)

            # Music symbols
            '\u266A': '*',  # ♪ -> *
            '\u266B': '*',  # ♫ -> *

            # Special symbols
            '\u2605': '*',  # ★ -> *
            '\u2606': '*',  # ☆ -> *
            '\u2665': '<3',  # ♥ -> <3
            '\u2660': '*',  # ♠ -> *
            '\u2663': '*',  # ♣ -> *
            '\u2666': '*',  # ♦ -> *

            # Arrows
            '\u2190': '<-',  # ← -> <-
            '\u2191': '^',  # ↑ -> ^
            '\u2192': '->',  # → -> ->
            '\u2193': 'v',  # ↓ -> v
            '\u2194': '<->',  # ↔ -> <->
            '\u21D2': '=>',  # ⇒ -> =>
            '\u21D4': '<=>',  # ⇔ -> <=>

            # Bullets and marks
            '\u2022': '*',  # • -> *
            '\u2026': '...',  # … -> ...
            '\u2018': "'",  # ' -> '
            '\u2019': "'",  # ' -> '
            '\u201C': '"',  # " -> "
            '\u201D': '"',  # " -> "

            # Math symbols
            '\u00B1': '+/-',  # ± -> +/-
            '\u00D7': 'x',  # × -> x
            '\u00F7': '/',  # ÷ -> /
            '\u221E': 'inf',  # ∞ -> inf
            '\u2260': '!=',  # ≠ -> !=
            '\u2264': '<=',  # ≤ -> <=
            '\u2265': '>=',  # ≥ -> >=
            '\u221A': 'sqrt',  # √ -> sqrt

            # Currency
            '\u20AC': 'EUR',  # € -> EUR
            '\u00A3': 'GBP',  # £ -> GBP
            '\u00A5': 'JPY',  # ¥ -> JPY
        }

        def replace_incompatible_chars(text):
            if not isinstance(text, str):
                return text

            for char, replacement in incompatible_chars.items():
                text = text.replace(char, replacement)
            return text

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
                    return formatted_data
            except Exception as e:
                logger.error(f"Error processing key {key}: {e}")
                return []

        def write_row(row):
            try:
                if isinstance(row, dict):
                    values = list(row.values())
                    return [replace_incompatible_chars(val) for val in values]
                elif isinstance(row, list):
                    return [replace_incompatible_chars(val) for val in row]
                else:
                    logger.warning(f"Invalid row format: {row}")
                    return None
            except Exception as e:
                logger.error(f"Error preparing row for CSV: {e}")
                return None

        sorted_keys = sorted(keys, key=lambda k: int(k.decode('utf-8').split(':')[1]) if k.decode('utf-8').split(':')[1].isdigit() else 0)
        
        all_rows = []
        for key in sorted_keys:
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
        client.set(csv_key_name, csv_buffer.getvalue().encode(encoding, errors='ignore'), ex=3600)
        return csv_key_name

    except Exception as e:
        logger.error(f"Critical error generating CSV file: {e}")
        return None


@shared_task
def generate_excel_task(excel_key_pattern, headers, sheet_name):
    try:
        client = redis_client.get_client()
        keys = list(redis_client.scan_keys(excel_key_pattern))

        if not keys:
            logger.warning("No formatted data found for Excel generation.")
            return None

        import pandas as pd
        import io
        from openpyxl import Workbook
        from openpyxl.utils.dataframe import dataframe_to_rows

        wb = Workbook()
        ws = wb.active

        ws.title = sheet_name

        ws.append(headers)

        all_rows = []

        sorted_keys = sorted(keys, key=lambda k: int(k.decode('utf-8').split(':')[1]) if k.decode('utf-8').split(':')[1].isdigit() else 0)
        
        for key in sorted_keys:
            try:
                data = client.get(key)
                if data:
                    formatted_data = json.loads(data)
                    all_rows.extend(formatted_data)
            except Exception as e:
                logger.error(f"Error processing key {key}: {e}")

        for row in all_rows:
            if isinstance(row, dict):
                ws.append(list(row.values()))
            elif isinstance(row, list):
                ws.append(row)
            else:
                logger.warning(f"Invalid row format: {row}")

        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(cell.value)
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
