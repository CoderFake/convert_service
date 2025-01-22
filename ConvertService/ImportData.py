import logging
import os
import hashlib
import django
from pathlib import Path
from configs.models import Migrations
from django.db import connection, transaction
from django.db import connections

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ConvertService.settings")
try:
    django.setup()
    logger.info("Django environment successfully initialized.")
except Exception as e:
    logger.error(f"Failed to initialize Django environment: {e}")
    exit(1)

def check_database_connection():
    try:
        connections['default'].cursor()
        logger.info("Database connection successful.")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        exit(1)

def calculate_file_hash(file_path):
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def import_sql_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as sql_file:
        sql_commands = sql_file.read()

    commands = sql_commands.split(';')

    with connection.cursor() as cursor:
        for command in commands:
            command = command.strip()
            if not command:
                continue

            if not ("INSERT INTO" in command.upper() or "UPDATE" in command.upper()):
                logger.warning(f"Skipping command: {command[:50]}...")
                continue

            try:
                cursor.execute(command)
            except Exception as e:
                logger.error(f"Failed to execute command: {command[:50]}... Error: {e}")

def extract_timestamp(file_name):

    base_name = file_name.split('-')[0]
    return base_name if base_name.isdigit() else "0"

def process_sql_files():
    data_dir = Path("data")
    logger.info(f"Checking data directory at: {data_dir.resolve()}")

    if not data_dir.exists():
        logger.error("Data directory does not exist.")
        return

    sql_files = list(data_dir.glob("*.sql"))
    if not sql_files:
        logger.info("No .sql files found in the data directory.")
        return

    sorted_sql_files = sorted(sql_files, key=lambda x: extract_timestamp(x.name))

    for sql_file in sorted_sql_files:
        logger.info(f"Processing file: {sql_file.name}")

        if sql_file.stat().st_size == 0:
            logger.info(f"Skipping {sql_file.name}: file is empty.")
            continue

        file_name = sql_file.name
        file_hash = calculate_file_hash(sql_file)

        if Migrations.objects.filter(name=file_name).exists():
            logger.info(f"Skipping {file_name}: already imported.")
            continue

        if Migrations.objects.filter(hash=file_hash).exists():
            logger.info(f"Skipping {file_name}: duplicate content.")
            continue

        try:
            with transaction.atomic():
                logger.info(f"Importing {file_name}...")
                import_sql_file(sql_file)

                Migrations.objects.create(name=file_name, hash=file_hash)
                logger.info(f"Successfully imported {file_name}.")
        except Exception as e:
            logger.error(f"Failed to import {file_name}: {e}")

logger.info("Script started.")
check_database_connection()
try:
    process_sql_files()
    logger.info("Script finished successfully.")
except Exception as e:
    logger.error(f"An unexpected error occurred: {e}")
