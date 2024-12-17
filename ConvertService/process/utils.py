import datetime
import os
import re
import csv
import json
import fitz
import xml.etree.ElementTree as ET
from pathlib import Path

import jaconv
from openpyxl import load_workbook
import redis
import logging
from home.dataclasses import PatientRecord

logger = logging.getLogger(__name__)

def get_redis_client():
    try:
        client = redis.StrictRedis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=int(os.getenv('REDIS_DB', 0))
        )
        return client
    except Exception as e:
        logger.error(f"Error initializing Redis client: {e}")
        raise


class FileProcessor:

    @staticmethod
    def process_file(file_path, output_path=None, mode='csv'):
        file_path = Path(file_path)
        if file_path.suffix == '.csv':
            return FileProcessor.process_csv(file_path, output_path, mode)
        elif file_path.suffix == '.json':
            return FileProcessor.process_json(file_path, output_path, mode)
        elif file_path.suffix == '.xml':
            return FileProcessor.process_xml(file_path, output_path, mode)
        elif file_path.suffix == '.xlsx':
            return FileProcessor.process_excel(file_path, output_path, mode)
        elif file_path.suffix == '.pdf':
            return FileProcessor.process_pdf(file_path, output_path, mode)
        else:
            raise ValueError(f"Unsupported file type: {file_path.suffix}")

    @staticmethod
    def write_to_csv(data, output_path):
        try:
            headers = list(PatientRecord.COLUMN_NAMES.values())
            output_path = Path(output_path)
            with output_path.open('w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)
                writer.writerows(data)
            logger.info(f"CSV file successfully created at: {output_path}")
        except Exception as e:
            logger.error(f"Error creating CSV file: {e}")
            raise

    @staticmethod
    def process_csv(file_path, output_path=None, mode='csv'):
        try:
            headers = list(PatientRecord.COLUMN_NAMES.values())
            with open(file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                data = [
                    [
                        row.get(header, "") or "" for header in headers
                    ]
                    for row in reader
                ]
            if mode == 'csv' and output_path:
                FileProcessor.write_to_csv(data, output_path)
                return f"CSVファイル {file_path} が正常に処理されました。"
            elif mode == 'dict':
                return data
        except Exception as e:
            logger.error(f"Error processing CSV file: {e}")
            return f"CSVファイルの処理エラー: {str(e)}"

    @staticmethod
    def process_json(file_path, output_path=None, mode='csv'):
        try:
            headers = list(PatientRecord.COLUMN_NAMES.values())
            with open(file_path, 'r', encoding='utf-8') as jsonfile:
                json_data = json.load(jsonfile)
                data = [
                    [
                        item.get(header, "") or "" for header in headers
                    ]
                    for item in json_data
                ]
            if mode == 'csv' and output_path:
                FileProcessor.write_to_csv(data, output_path)
                return f"JSONファイル {file_path} が正常に処理されました。"
            elif mode == 'dict':
                return data
        except Exception as e:
            logger.error(f"Error processing JSON file: {e}")
            return f"JSONファイルの処理エラー: {str(e)}"

    @staticmethod
    def process_xml(file_path, output_path=None, mode='csv'):
        try:
            headers = list(PatientRecord.COLUMN_NAMES.values())
            tree = ET.parse(file_path)
            root = tree.getroot()
            data = [
                [
                    (elem.find(header).text or "") if elem.find(header) is not None else ""
                    for header in headers
                ]
                for elem in root.findall('.//record')
            ]
            if mode == 'csv' and output_path:
                FileProcessor.write_to_csv(data, output_path)
                return f"XMLファイル {file_path} が正常に処理されました。"
            elif mode == 'dict':
                return data
        except Exception as e:
            logger.error(f"Error processing XML file: {e}")
            return f"XMLファイルの処理エラー: {str(e)}"

    @staticmethod
    def process_excel(file_path, output_path=None, mode='csv'):
        try:
            headers = list(PatientRecord.COLUMN_NAMES.values())
            workbook = load_workbook(file_path)
            sheet = workbook.active
            data = [
                [
                    cell if cell is not None else "" for cell in row
                ]
                for row in sheet.iter_rows(values_only=True)
            ]
            if mode == 'csv' and output_path:
                FileProcessor.write_to_csv(data, output_path)
                return f"Excelファイル {file_path} が正常に処理されました。"
            elif mode == 'dict':
                return data
        except Exception as e:
            logger.error(f"Error processing Excel file: {e}")
            return f"Excelファイルの処理エラー: {str(e)}"

    @staticmethod
    def process_pdf(file_path, output_path=None, mode='csv'):
        try:
            headers = list(PatientRecord.COLUMN_NAMES.values())
            keys = list(PatientRecord.COLUMN_NAMES.keys())
            data = []
            pdf_document = fitz.open(file_path)
            for page in pdf_document:
                row = [""] * len(headers)
                form_fields = page.widgets()
                if form_fields:
                    for widget in form_fields:
                        field_name = widget.field_name
                        field_value = widget.field_value or ""
                        if field_name in keys:
                            index = keys.index(field_name)
                            row[index] = field_value
                data.append(row)
            pdf_document.close()
            if mode == 'csv' and output_path:
                FileProcessor.write_to_csv(data, output_path)
                return f"PDFファイル {file_path} が正常に処理されました。"
            elif mode == 'dict':
                return data
        except Exception as e:
            logger.error(f"Error processing PDF file: {e}")
            return f"PDFファイルの処理エラー: {str(e)}"


class DataFormatter:
    """
    A class to perform various data transformations and file formatting tasks.
    """
    RULE_MAPPING = {
        "CR_NOT_CHANGE": lambda value: value,
        "CR_DATE1": lambda value: DataFormatter.convert_date(value, '%Y/%m/%d'),
        "CR_DATE2": lambda value: DataFormatter.convert_date(value, '%Y-%m-%d'),
        "CR_G_12": lambda value: DataFormatter.convert_gender(value, '12'),
        "CR_G_MF": lambda value: DataFormatter.convert_gender(value, 'MF'),
        "CR_KANA_F-H": lambda value: DataFormatter.convert_kana(value, 'full_to_half'),
        "CR_KANA_H-F": lambda value: DataFormatter.convert_kana(value, 'half_to_full'),
        "CR_POSTAL_FORMAT": lambda value: DataFormatter.convert_postal_code(value),
    }

    @staticmethod
    def format_data_with_rules(data, rules, headers):
        formatted_data = []
        try:
            for row in data:
                formatted_row = row.copy()
                for rule_id, before_column, after_column in rules:
                    try:
                        column_index = headers.index(before_column)
                        value = row[column_index] if column_index < len(row) else ""
                        formatted_value = DataFormatter.apply_rule(value, rule_id)
                        formatted_row[column_index] = formatted_value

                    except ValueError:
                        logger.warning(f"Column '{before_column}' not found in headers.")
                formatted_data.append(formatted_row)
            return formatted_data
        except Exception as e:
            logger.error(f"Error formatting data with rules: {e}")
            return []

    @staticmethod
    def apply_rule(value, rule_id):
        """
        Apply transformation rule to a value.
        """
        try:
            rule_function = DataFormatter.RULE_MAPPING.get(rule_id, lambda v: v)
            return rule_function(value)
        except Exception as e:
            logger.error(f"Error applying rule {rule_id} to value {value}: {e}")
            return value



    @staticmethod
    def convert_date(value, target_format='%Y/%m/%d'):
        """
        Supported target formats:
        - 'yyyy/MM/dd'
        - 'yyyy-MM-dd'

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

            if date_result:
                return date_result.strftime('%Y/%m/%d' if target_format == '%Y/%m/%d' else '%Y-%m-%d')

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
        - 'full_to_half': Convert full-width to half-width.
        - 'half_to_full': Convert half-width to full-width.
        """
        try:
            if not value:
                return ""
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

