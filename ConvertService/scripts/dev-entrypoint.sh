#!/bin/bash

mkdir -p /home/ConvertService/locale

echo "Running makemigrations..."
if ! python manage.py makemigrations; then
    echo "Error during makemigrations."
    exit 1
fi

echo "Running migrate..."
if ! python manage.py migrate; then
    echo "Error during migration."
    exit 1
fi

echo "Running ImportData.py..."
if ! python manage.py shell < ImportData.py; then
    echo "Error during ImportData.py execution."
    exit 1
fi

echo "Collecting static files..."
if ! python manage.py collectstatic --noinput --clear; then
    echo "Error during collectstatic."
    exit 1
fi

echo "Generating translation messages..."
if ! python manage.py makemessages -l ja; then
    echo "Error during makemessages."
    exit 1
fi

echo "Compiling translation messages..."
if ! python manage.py compilemessages; then
    echo "Error during compilemessages."
    exit 1
fi

echo "Creating superuser..."
if ! python create_superuser.py; then
    echo "Error during superuser creation."
    exit 1
fi

echo "Starting the development server..."
if ! python manage.py runserver 0.0.0.0:8000; then
    echo "Error during runserver."
    exit 1
fi
