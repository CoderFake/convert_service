#!/bin/bash
set -e

until mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -e "SELECT 1"; do
  echo "Waiting for MySQL..."
  sleep 5
done

mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -e "CREATE DATABASE IF NOT EXISTS \`${MYSQL_DATABASE}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

echo "Database ${MYSQL_DATABASE} created successfully."
