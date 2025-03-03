import datetime
import os
import re
import csv
import json
import fitz
import xml.etree.ElementTree as ET
from pathlib import Path
import pandas as pd
import jaconv
from PyPDF2 import PdfReader
from openpyxl import load_workbook
from concurrent.futures import ThreadPoolExecutor
import logging
from .fetch_data import RuleFixedID, FixedValueFetcher

logger = logging.getLogger(__name__)


class DisplayData:
    @staticmethod
    def filter_list(headers, hidden_headers, data):
        """
        Filter headers and data based on visible headers.
        """
        try:
            visible_indices = [i for i, header in enumerate(headers) if header not in hidden_headers]
            filtered_headers = [header for i, header in enumerate(headers) if i in visible_indices]

            filtered_data = []
            for row in data:
                if len(row) < len(headers):
                    logger.warning(f"Skipping row due to mismatched length: {row}")
                    continue
                try:
                    filtered_row = [row[i] if i < len(row) else "" for i in visible_indices]
                    filtered_data.append(filtered_row)
                except IndexError as e:
                    logger.error(f"Error accessing row: {row}, error: {e}")
                    continue

            return filtered_headers, filtered_data
        except Exception as e:
            logger.error(f"Error filtering data: {e}")
            return [], []

    @staticmethod
    def get_list_data(redis_client, keys, hidden_formatted_header):
        try:
            visible_indices = [
                header.get('index_value') for header in hidden_formatted_header
                if header.get('index_value', False)
            ]

            result = []
            max_workers = os.cpu_count() or 4

            for key in keys:
                try:
                    raw_data = redis_client.get(key)
                    if raw_data:
                        data = json.loads(raw_data.decode('utf-8'))
                        with ThreadPoolExecutor(max_workers=max_workers) as executor:
                            filtered_rows = []
                            futures = []

                            def remove_columns(row):
                                indices_to_remove = sorted(visible_indices, reverse=True)
                                new_row = list(row)
                                for idx in indices_to_remove:
                                    if idx < len(new_row):
                                        new_row.pop(idx)
                                return new_row

                            for row in data:
                                futures.append(
                                    executor.submit(remove_columns, row)
                                )

                            for future in futures:
                                try:
                                    filtered_row = future.result()
                                    if filtered_row:
                                        filtered_rows.append(filtered_row)
                                except Exception as e:
                                    logger.error(f"Error processing row: {e}")
                                    continue

                        if filtered_rows:
                            result.append({
                                "data": filtered_rows,
                                "key": key.decode('utf-8')
                            })
                except Exception as e:
                    logger.error(f"Error reading formatted data from Redis key {key}: {e}")
                    return []

            return result
        except Exception as e:
            logger.error(f"Error combining formatted data: {e}")
            return []


class FileFormatMapper:
    FORMAT_MAPPING = {
        'CSV_C_SJIS': {'delimiter': ',', 'encoding': 'shift_jis'},
        'CSV_C_UTF-8': {'delimiter': ',', 'encoding': 'utf-8'},
        'CSV_T_SJIS': {'delimiter': '\t', 'encoding': 'shift_jis'},
        'CSV_T_UTF-8': {'delimiter': '\t', 'encoding': 'utf-8'},
    }

    @staticmethod
    def get_format_details(file_format_id: str):
        return FileFormatMapper.FORMAT_MAPPING.get(file_format_id, None)


class FileProcessor:
    Fallback_Encodings = ['utf-8', 'shift_jis', 'cp932', 'iso-8859-1']

    @staticmethod
    def process_file(file_path, headers, mode='dict', file_format_id=None):
        file_path = Path(file_path)
        if file_path.suffix == '.csv':
            return FileProcessor.process_csv(file_path, headers, mode, file_format_id)
        elif file_path.suffix == '.json':
            return FileProcessor.process_json(file_path, headers, mode)
        elif file_path.suffix == '.xml':
            return FileProcessor.process_xml(file_path, headers, mode)
        elif file_path.suffix == '.xlsx':
            return FileProcessor.process_excel(file_path, headers, mode)
        elif file_path.suffix == '.pdf':
            return FileProcessor.process_pdf(file_path, headers, mode)
        else:
            raise ValueError(f"Unsupported file type: {file_path.suffix}")

    @staticmethod
    def process_csv(file_path, headers, mode, file_format_id):
        """
        Process CSV files with fallback for different encodings.
        """
        try:
            format_details = FileFormatMapper.get_format_details(file_format_id)
            if not format_details:
                raise ValueError(f"Unsupported file format: {file_format_id}")

            delimiter = format_details['delimiter']
            primary_encoding = format_details['encoding']

            try:
                return FileProcessor._read_csv(file_path, headers, mode, delimiter, primary_encoding)
            except UnicodeDecodeError as e:
                logger.warning(f"Primary encoding {primary_encoding} failed for CSV. Error: {e}")

            for encoding in FileProcessor.Fallback_Encodings:
                if encoding != primary_encoding:
                    try:
                        logger.info(f"Trying fallback encoding {encoding} for CSV.")
                        return FileProcessor._read_csv(file_path, headers, mode, delimiter, encoding)
                    except UnicodeDecodeError as e:
                        logger.warning(f"Encoding {encoding} failed for CSV. Error: {e}")

            raise ValueError("Failed to process CSV file with all attempted encodings.")
        except Exception as e:
            logger.error(f"Error processing CSV file {file_path}: {e}")
            raise

    @staticmethod
    def process_json(file_path, headers, mode):
        """
        Process JSON files with fallback for different encodings.
        """
        try:
            for encoding in FileProcessor.Fallback_Encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as jsonfile:
                        json_data = json.load(jsonfile)
                        return FileProcessor._map_data(json_data, headers, mode)
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.warning(f"Error decoding JSON with encoding {encoding}: {e}")
            raise ValueError("Failed to process JSON file with all attempted encodings.")
        except Exception as e:
            logger.error(f"Error processing JSON file {file_path}: {e}")
            raise

    @staticmethod
    def process_xml(file_path, headers, mode):
        """
        Process XML files with fallback for different encodings.
        """
        try:
            for encoding in FileProcessor.Fallback_Encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as xmlfile:
                        tree = ET.parse(xmlfile)
                        root = tree.getroot()
                        return FileProcessor._map_xml(root, headers, mode)
                except (ET.ParseError, UnicodeDecodeError) as e:
                    logger.warning(f"Error parsing XML with encoding {encoding}: {e}")
            raise ValueError("Failed to process XML file with all attempted encodings.")
        except Exception as e:
            logger.error(f"Error processing XML file {file_path}: {e}")
            raise

    @staticmethod
    def process_excel(file_path, headers, mode):
        """
        Process Excel files.
        """
        try:
            workbook = load_workbook(file_path)
            sheet = workbook.active
            return FileProcessor._map_excel(sheet, headers, mode)
        except KeyError as e:
            logger.error(f"Missing headers in Excel file: {e}")
            raise
        except Exception as e:
            logger.error(f"Error processing Excel file {file_path}: {e}")
            raise

    @staticmethod
    def process_pdf(file_path, headers, mode):
        """
        Process PDF files with structured data extraction.
        """
        try:
            pdf_document = fitz.open(file_path)
            data = []
            for page in pdf_document:
                row = ["" for _ in headers]
                form_fields = page.widgets()
                if form_fields:
                    for widget in form_fields:
                        field_name = widget.field_name
                        field_value = widget.field_value or ""
                        if field_name in headers:
                            index = headers.index(field_name)
                            row[index] = field_value
                if mode == 'dict':
                    data.append({headers[i]: row[i] for i in range(len(headers))})
                elif mode == 'csv':
                    data.append(row)
            pdf_document.close()
            if mode == 'csv':
                data.insert(0, headers)
            return data
        except Exception as e:
            logger.error(f"Error processing PDF file {file_path}: {e}")
            raise

    @staticmethod
    def _read_csv(file_path, headers, mode, delimiter, encoding):
        """
        Helper method to read CSV files with flexible encoding and handle row-level errors.
        """
        try:
            with open(file_path, 'r', encoding=encoding) as csvfile:
                reader = csv.DictReader(csvfile, delimiter=delimiter)
                data = []
                for row_idx, row in enumerate(reader):
                    try:
                        data.append([row.get(header, "") for header in headers])
                    except Exception as row_error:
                        logger.warning(f"Error processing row {row_idx + 1}: {row_error}. Skipping this row.")
                        continue

                if mode == 'csv':
                    data.insert(0, headers)

            logger.info(f"Successfully read CSV with encoding {encoding}.")
            return data
        except UnicodeDecodeError as e:
            logger.warning(f"Failed to read CSV with encoding {encoding}: {e}")
            raise

    @staticmethod
    def _map_data(data, headers, mode):
        """
        Helper method to map data to headers for JSON and other formats.
        """
        mapped_data = []
        for item in data:
            if mode == 'dict':
                mapped_data.append({header: item.get(header, "") for header in headers})
            elif mode == 'csv':
                mapped_data.append([item.get(header, "") for header in headers])
        if mode == 'csv':
            mapped_data.insert(0, headers)
        return mapped_data

    @staticmethod
    def _map_xml(root, headers, mode):
        """
        Helper method to map XML data to headers.
        """
        data = []
        for elem in root.findall('.//record'):
            if mode == 'dict':
                data.append({header: elem.find(header).text if elem.find(header) else "" for header in headers})
            elif mode == 'csv':
                data.append([elem.find(header).text if elem.find(header) else "" for header in headers])
        if mode == 'csv':
            data.insert(0, headers)
        return data

    @staticmethod
    def _map_excel(sheet, headers, mode):
        """
        Helper method to map Excel data to headers.
        """
        header_indices = {header: idx for idx, header in enumerate(sheet[1])}
        data = []
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if mode == 'dict':
                data.append({header: row[header_indices[header]] if header in header_indices else "" for header in headers})
            elif mode == 'csv':
                data.append([row[header_indices[header]] if header in header_indices else "" for header in headers])
        if mode == 'csv':
            data.insert(0, headers)
        return data


class DataFormatter:
    """
    A class to perform various data transformations and file formatting tasks.
    """
    class RuleFixedMapping(RuleFixedID):
        pass

    RULE_MAPPING = {
        "CR_NOT_CHANGE": lambda value: value,
        "CR_DATE1": lambda value: DataFormatter.convert_date(value, '%Y/%m/%d'),
        "CR_DATE2": lambda value: DataFormatter.convert_date(value, '%Y-%m-%d'),
        "CR_G_12": lambda value: DataFormatter.convert_gender(value, '12'),
        "CR_G_MF": lambda value: DataFormatter.convert_gender(value, 'MF'),
        "CR_KANA_F-H": lambda value: DataFormatter.convert_kana(value, 'full_to_half'),
        "CR_KANA_H-F": lambda value: DataFormatter.convert_kana(value, 'half_to_full'),
        "CR_POSTAL_FORMAT": lambda value: DataFormatter.convert_postal_code(value),
        "CR_TIME": lambda value: DataFormatter.convert_time(value),
    }

    @staticmethod
    def apply_rule(value, rule_id):
        try:
            rule_function = DataFormatter.RULE_MAPPING.get(rule_id, lambda v: v)
            transformed_value = rule_function(value)
            return transformed_value
        except Exception as e:
            logger.error(f"Error applying rule {rule_id} to value {value}: {e}")
            return value

    @staticmethod
    def is_fixed_rule(rule_id):
        return rule_id in DataFormatter.RuleFixedMapping.get_values()

    @staticmethod
    def format_data_with_rules(row, rules, before_headers, after_headers, tenant_id):
        try:
            mapped_row = [""] * len(after_headers)
            before_indices = [h['index_value'] for h in before_headers]

            for rule_id, idx_before, idx_after in rules:
                if idx_after < len(after_headers):
                    if idx_before < len(row):
                        value = row[idx_before]
                        if idx_before in before_indices:
                            mapped_row[idx_after] = value
                        else:
                            mapped_row[idx_after] = ""
                    else:
                        mapped_row[idx_after] = ""

            for rule_id, idx_before, idx_after in rules:
                if idx_after < len(mapped_row):
                    if DataFormatter.is_fixed_rule(rule_id):
                        mapped_row[idx_after] = DataFormatter.convert_fixed_value(
                            mapped_row[idx_after], rule_id, tenant_id
                        )
                    else:
                        mapped_row[idx_after] = DataFormatter.apply_rule(
                            mapped_row[idx_after], rule_id
                        )

            return mapped_row

        except Exception as e:
            logger.error(f"Error formatting row with rules: {e}")
            return []

    @staticmethod
    def convert_fixed_value(value, rule_id, tenant_id):
        try:
            after_value = FixedValueFetcher.get_value_mapping(tenant_id, rule_id, value)

            return after_value if after_value else value

        except Exception as e:
            logger.error(f"Error in convert_fixed_value for rule {rule_id}, tenant {tenant_id}: {value} -> {e}")
            return value


    @staticmethod
    def convert_date(value, target_format='%Y/%m/%d'):
        """
        Convert a date string to the desired format.
        Supported formats:
        - Japanese Era formats
        - ISO formats (YYYY/MM/DD, YYYY-MM-DD)
        - Kanji dates (YYYY年MM月DD日)
        - US-style formats (MM/DD/YYYY, MM-DD-YYYY)
        - Custom formats like DD/MM/YYYY, YYYY\DD\MM

        :param value: The date value to be converted
        :param target_format: The desired output format
        :return: Formatted date string or original value if conversion fails
        """
        try:
            if not value or not isinstance(value, str):
                return ""

            value = value.strip()
            date_result = None

            # 1. Handle Japanese Era formats
            era_map = {"S": 1925, "H": 1988, "R": 2018}
            era_match = re.match(r'([S|H|R])\s*(\d{1,2})[.\-年](\d{1,2})[.\-月](\d{1,2})日?', value)
            if era_match:
                era, year, month, day = era_match.groups()
                base_year = era_map.get(era[0], 0)
                year = int(year) + base_year
                date_result = datetime.datetime(year, int(month), int(day))

            kanji_era_match = re.match(r'(昭和|平成|令和)\s*(\d{1,2})[.\-年](\d{1,2})[.\-月](\d{1,2})日?', value)
            if kanji_era_match:
                kanji_era, year, month, day = kanji_era_match.groups()
                era = {"昭和": 1925, "平成": 1988, "令和": 2018}[kanji_era]
                year = int(year) + era
                date_result = datetime.datetime(year, int(month), int(day))

            # 2. Handle ISO-like formats
            if not date_result:
                iso_match = re.match(r'(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})', value)
                if iso_match:
                    year, month, day = map(int, iso_match.groups())
                    date_result = datetime.datetime(year, month, day)

            # 3. Handle Kanji dates
            if not date_result:
                kanji_match = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日', value)
                if kanji_match:
                    year, month, day = map(int, kanji_match.groups())
                    date_result = datetime.datetime(year, month, day)

            # 4. Handle US-style formats with time
            if not date_result:
                us_match_with_time = re.match(
                    r'(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})\s(\d{1,2}):(\d{1,2}):(\d{1,2})\s(AM|PM)', value)
                if us_match_with_time:
                    month, day, year, hour, minute, second, period = us_match_with_time.groups()
                    hour = int(hour)
                    if period == 'PM' and hour != 12:
                        hour += 12
                    elif period == 'AM' and hour == 12:
                        hour = 0
                    date_result = datetime.datetime(int(year), int(month), int(day), hour, int(minute), int(second))

            # 5. Handle US-style formats without time (e.g., MM/DD/YYYY or MM-DD-YYYY)
            if not date_result:
                us_match = re.match(r'(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})', value)
                if us_match:
                    month, day, year = map(int, us_match.groups())
                    date_result = datetime.datetime(year, month, day)

            # 6. Handle DD/MM/YYYY or YYYY\DD\MM
            if not date_result:
                custom_match = re.match(r'(\d{1,2})[\/\-\\](\d{1,2})[\/\-\\](\d{4})', value)
                if custom_match:
                    day, month, year = map(int, custom_match.groups())
                    date_result = datetime.datetime(year, month, day)

            if not date_result:
                reverse_match = re.match(r'(\d{4})[\/\-\\](\d{1,2})[\/\-\\](\d{1,2})', value)
                if reverse_match:
                    year, day, month = map(int, reverse_match.groups())
                    date_result = datetime.datetime(year, month, day)

            # 7. Convert to the desired format
            if date_result:
                if target_format == '%d/%m/%Y':
                    return date_result.strftime('%d/%m/%Y')
                return date_result.strftime(target_format)

            return value
        except Exception as e:
            logger.error(f"Error converting date: {value} -> {e}")
            return value

    @staticmethod
    def convert_gender(value, gender_type='12'):
        """
        Convert gender format based on the specified type.

        Supported types:
        - '12': Male = 1, Female = 2
        - 'MF': Male = M, Female = F
        - 'KANJI': Male = 男, Female = 女
        - 'KANJI_FULL': Male = 男性, Female = 女性
        """
        try:
            gender_map = {
                '12': {"男": "1", "女": "2", "男性": "1", "女性": "2", "1": "1", "2": "2"},
                'MF': {"男": "M", "女": "F", "男性": "M", "女性": "F", "M": "M", "F": "F"},
                'KANJI': {"1": "男", "2": "女", "M": "男", "F": "女", "男性": "男", "女性": "女"},
                'KANJI_FULL': {"1": "男性", "2": "女性", "M": "男性", "F": "女性", "男": "男性", "女": "女性"},
            }

            return gender_map.get(gender_type, {}).get(value, value)
        except Exception as e:
            logger.error(f"Error in convert_gender: {e}")
            return ""

    @staticmethod
    def convert_kana(value, kana_type='full_to_half'):
        """
        Convert Kana between full-width and half-width.
        - 'full_to_half': Convert full-width Kana to half-width.
        - 'half_to_full': Convert half-width Kana to full-width.
        """
        try:
            if not value:
                return ""

            # Convert Hiragana (or mixed Hiragana + Katakana) to Katakana
            value = jaconv.hira2kata(value)

            if kana_type == 'full_to_half':
                return jaconv.z2h(value, kana=True)
            elif kana_type == 'half_to_full':
                return jaconv.h2z(value, kana=True)
            else:
                logger.warning(f"Unsupported kana type: {kana_type}")
                return value
        except Exception as e:
            logger.error(f"Error in convert_kana: {e}")
            return ""


    @staticmethod
    def convert_postal_code(value):
        """
        Automatically detects and converts various postal code formats to a standard format (XXX-XXXX).

        :param value: The postal code value to be converted
        :return: Standardized postal code or original value if conversion fails
        """
        try:
            if not value or not isinstance(value, str):
                return ""

            value = value.strip()
            value = re.sub(r"[^\d\-]", "", value)

            postal_match = re.match(r"(\d{3})[-\s]?(\d{4})", value)
            if postal_match:
                return f"{postal_match.group(1)}-{postal_match.group(2)}"

            continuous_digits_match = re.match(r"(\d{3})(\d{4})", value)
            if continuous_digits_match:
                return f"{continuous_digits_match.group(1)}-{continuous_digits_match.group(2)}"

            return value
        except Exception as e:
            logger.error(f"Error converting postal code: {value} -> {e}")
            return value

    @staticmethod
    def convert_time(value):
        """
        Convert time from hh:mm to custom format:
        - hh:01 -> hh:15 => hh15
        - hh:16 -> hh:30 => hh30
        - hh:31 -> hh:45 => hh45
        - hh:46 -> hh:00 => hh00

        :param value: The time value to be converted
        :return: Formatted time or original value if conversion fails
        """
        try:
            if not value or not isinstance(value, str):
                return ""

            value = value.strip()
            time_match = re.match(r"(\d{1,2}):(\d{2})", value)
            if not time_match:
                return value

            hour, minute = map(int, time_match.groups())

            if 1 <= minute <= 15:
                return f"{hour:02d}15"
            elif 16 <= minute <= 30:
                return f"{hour:02d}30"
            elif 31 <= minute <= 45:
                return f"{hour:02d}45"
            elif 46 <= minute <= 59 or minute == 0:
                next_hour = (hour + 1) % 24 if minute >= 46 else hour
                return f"{next_hour:02d}00"

            return value
        except Exception as e:
            logger.error(f"Error converting time: {value} -> {e}")
            return value


    @staticmethod
    def write_dict(data, file_paths):

        results = {}
        try:
            for index, (key, path) in enumerate(file_paths.items()):
                try:
                    with open(path, 'w', encoding='utf-8') as jsonfile:
                        json.dump(data[index], jsonfile, ensure_ascii=False, indent=4)
                    results[key] = f"Successfully created file at {path}"
                except Exception as e:
                    logger.error(f"Error writing to file {path}: {e}")
                    results[key] = f"Error: {str(e)}"
            return results
        except Exception as e:
            logger.error(f"Error in write_dict: {e}")
            return {"error": str(e)}

    @staticmethod
    def write_csv(data, file_path, delimiter=',', encoding='utf-8'):
        try:
            with open(file_path, 'w', newline='', encoding=encoding) as csvfile:
                writer = csv.writer(csvfile, delimiter=delimiter)
                writer.writerows(data)
            logger.info(f"CSV file successfully created: {file_path}")
            return f"CSV file successfully created: {file_path}"
        except Exception as e:
            logger.error(f"Error writing CSV file: {file_path} - {e}")
            return f"CSV file creation error: {e}"

    @staticmethod
    def write_json(data, file_path):
        """
        Write data to a JSON file.
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as jsonfile:
                json.dump(data, jsonfile, ensure_ascii=False, indent=4)
            logger.info(f"JSON file successfully created: {file_path}")
            return f"JSON file successfully created: {file_path}"
        except Exception as e:
            logger.error(f"Error writing JSON file: {file_path} - {e}")
            return f"JSON file creation error: {e}"

    @staticmethod
    def write_xml(data, file_path):
        """
        Write data to an XML file.
        """
        try:
            root = ET.Element("root")
            for row in data:
                item = ET.SubElement(root, "record")
                for i, value in enumerate(row):
                    ET.SubElement(item, f"field{i+1}").text = value

            tree = ET.ElementTree(root)
            tree.write(file_path, encoding="utf-8", xml_declaration=True)
            logger.info(f"XML file successfully created: {file_path}")
            return f"XML file successfully created: {file_path}"
        except Exception as e:
            logger.error(f"Error writing XML file: {file_path} - {e}")
            return f"XML file creation error: {e}"

    @staticmethod
    def format_file(data, file_format, file_path):
        """
        Format file output based on the specified format.
        Supported formats: CSV, JSON, XML.
        """
        try:
            if file_format == 'CSV_C_SJIS':
                return DataFormatter.write_csv(data, file_path, delimiter=',', encoding='shift_jis')
            elif file_format == 'CSV_C_UTF-8':
                return DataFormatter.write_csv(data, file_path, delimiter=',', encoding='utf-8')
            elif file_format == 'CSV_T_SJIS':
                return DataFormatter.write_csv(data, file_path, delimiter='\t', encoding='shift_jis')
            elif file_format == 'CSV_T_UTF-8':
                return DataFormatter.write_csv(data, file_path, delimiter='\t', encoding='utf-8')
            elif file_format == 'JSON':
                return DataFormatter.write_json(data, file_path)
            elif file_format == 'XML':
                return DataFormatter.write_xml(data, file_path)
            else:
                logger.error(f"Unsupported file format: {file_format}")
                return f"Unsupported file format: {file_format}"
        except Exception as e:
            logger.error(f"Error formatting file: {file_path} - {e}")
            return f"File formatting error: {e}"


class ProcessHeader:

    @staticmethod
    def get_csv_header(file, delimiter, encoding):
        try:
            file.seek(0)
            reader = csv.reader(file.read().decode(encoding).splitlines(), delimiter=delimiter)
            header = next(reader)
            return [col.strip() for col in header]
        except Exception as e:
            logger.error(f"Error reading CSV header: {e}")
            return []

    @staticmethod
    def get_pdf_header(file):
        try:
            file.seek(0)
            reader = PdfReader(file)
            fields = reader.get_form_text_fields()
            return [field.strip() for field in fields.keys()] if fields else []
        except Exception as e:
            logger.error(f"Error reading PDF header: {e}")
            return []

    @staticmethod
    def get_excel_header(file):
        try:
            file.seek(0)
            df = pd.read_excel(file, nrows=0)
            return [col.strip() for col in df.columns]
        except Exception as e:
            logger.error(f"Error reading Excel header: {e}")
            return []

    @staticmethod
    def get_json_header(file):
        try:
            file.seek(0)
            data = json.load(file)
            if isinstance(data, list) and len(data) > 0:
                return [key.strip() for key in data[0].keys()]
            elif isinstance(data, dict):
                return [key.strip() for key in data.keys()]
            return []
        except Exception as e:
            logger.error(f"Error reading JSON header: {e}")
            return []

    @staticmethod
    def get_xml_header(file):
        try:
            file.seek(0)
            tree = ET.parse(file)
            root = tree.getroot()
            return [elem.tag.strip() for elem in root[0]] if len(root) > 0 else []
        except Exception as e:
            logger.error(f"Error reading XML header: {e}")
            return []

    @staticmethod
    def get_header(file, file_type):
        format_details = FileFormatMapper.get_format_details(file_type)
        if not format_details:
            logger.error(f"Unsupported file type: {file_type}")
            return []

        if file_type.startswith("CSV"):
            return ProcessHeader.get_csv_header(
                file,
                delimiter=format_details['delimiter'],
                encoding=format_details['encoding']
            )
        elif file_type == "PDF":
            return ProcessHeader.get_pdf_header(file)
        elif file_type == "Excel":
            return ProcessHeader.get_excel_header(file)
        elif file_type == "JSON":
            return ProcessHeader.get_json_header(file)
        elif file_type == "XML":
            return ProcessHeader.get_xml_header(file)
        else:
            logger.error(f"Unsupported file type: {file_type}")
            return []
