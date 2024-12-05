#!/bin/bash
set -e

until mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -e "SELECT 1"; do
  echo "Waiting for MariaDB..."
  sleep 5
done

mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -e "CREATE DATABASE IF NOT EXISTS ${DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

echo "Database ${DB_NAME} created successfully."
