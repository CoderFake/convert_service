import os
import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from openpyxl import load_workbook
from PyPDF2 import PdfReader
from celery import shared_task
import redis
import logging

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

    def __init__(self, file_path):
        self.file_path = Path(file_path)

    @staticmethod
    @shared_task
    def convert_to_csv(data, output_path):
        try:
            output_path = Path(output_path)
            if not isinstance(data, list):
                raise ValueError("Data must be a list of rows (iterable).")

            with output_path.open('w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(data)

            return f"データをCSVに正常に変換しました: {output_path}。"
        except Exception as e:
            logger.error(f"Error converting to CSV: {e}")
            return f"CSVへの変換エラー: {str(e)}"

    @staticmethod
    @shared_task
    def process_csv(file_path, output_path):
        try:
            logger.info(f"Processing CSV file: {file_path}")
            file_path = Path(file_path)
            with file_path.open('r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                data = list(reader)
                FileProcessor.convert_to_csv(data, output_path)
            return f"CSVファイル {file_path} が正常に処理され、変換されました。"
        except Exception as e:
            logger.error(f"Error processing CSV file: {e}")
            return f"CSVファイルの処理エラー: {str(e)}"

    @staticmethod
    @shared_task
    def process_pdf(file_path, output_path):
        try:
            logger.info(f"Processing PDF file: {file_path}")
            file_path = Path(file_path)
            reader = PdfReader(file_path)
            data = [[page.extract_text()] for page in reader.pages]
            FileProcessor.convert_to_csv(data, output_path)
            return f"PDFファイル {file_path} が正常に処理され、CSVに変換されました。"
        except Exception as e:
            logger.error(f"Error processing PDF file: {e}")
            return f"PDFファイルの処理エラー: {str(e)}"

    @staticmethod
    @shared_task
    def process_xml(file_path, output_path):
        try:
            logger.info(f"Processing XML file: {file_path}")
            file_path = Path(file_path)
            tree = ET.parse(file_path)
            root = tree.getroot()
            data = [[elem.tag, elem.text] for elem in root.iter()]
            FileProcessor.convert_to_csv(data, output_path)
            return f"XMLファイル {file_path} が正常に処理され、CSVに変換されました。"
        except Exception as e:
            logger.error(f"Error processing XML file: {e}")
            return f"XMLファイルの処理エラー: {str(e)}"

    @staticmethod
    @shared_task
    def process_excel(file_path, output_path):
        try:
            logger.info(f"Processing Excel file: {file_path}")
            file_path = Path(file_path)
            workbook = load_workbook(file_path)
            sheet = workbook.active
            data = [[cell for cell in row] for row in sheet.iter_rows(values_only=True)]
            FileProcessor.convert_to_csv(data, output_path)
            return f"Excelファイル {file_path} が正常に処理され、CSVに変換されました。"
        except Exception as e:
            logger.error(f"Error processing Excel file: {e}")
            return f"Excelファイルの処理エラー: {str(e)}"

    @staticmethod
    @shared_task
    def process_json(file_path, output_path):
        try:
            logger.info(f"Processing JSON file: {file_path}")
            file_path = Path(file_path)
            with file_path.open('r', encoding='utf-8') as jsonfile:
                data = json.load(jsonfile)
                if isinstance(data, list):
                    rows = [list(item.values()) for item in data]
                    headers = list(data[0].keys()) if data else []
                    rows.insert(0, headers)
                else:
                    rows = [[key, value] for key, value in data.items()]
                FileProcessor.convert_to_csv(rows, output_path)
            return f"JSONファイル {file_path} が正常に処理され、CSVに変換されました。"
        except Exception as e:
            logger.error(f"Error processing JSON file: {e}")
            return f"JSONファイルの処理エラー: {str(e)}"

    @staticmethod
    def process_file(file_path, output_path):
        file_path = Path(file_path)
        try:
            logger.info(f"Determining file type for: {file_path}")
            if file_path.suffix == '.csv':
                result = FileProcessor.process_csv.run(str(file_path), str(output_path))
            elif file_path.suffix == '.pdf':
                result = FileProcessor.process_pdf.run(str(file_path), str(output_path))
            elif file_path.suffix == '.xml':
                result = FileProcessor.process_xml.run(str(file_path), str(output_path))
            elif file_path.suffix == '.xlsx':
                result = FileProcessor.process_excel.run(str(file_path), str(output_path))
            elif file_path.suffix == '.json':
                result = FileProcessor.process_json.run(str(file_path), str(output_path))
            else:
                result = f"サポートされていないファイルタイプ: {file_path}"
            logger.info(f"File processed: {file_path} -> {output_path}")
            return result
        except Exception as e:
            logger.error(f"Error processing file: {e}")
            return f"ファイル処理エラー: {str(e)}"

