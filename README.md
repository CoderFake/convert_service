# P-017_ReservationConvertService


## Overview

- Python version: >= 3.10
- Configuration file: `P-017_ReservationConvertService/.env` and `P-017_ReservationConvertService/ConvertService/.env.{name}` 
- For local environment settings, create a `P-017_ReservationConvertService/ConvertService/.env.dev` file to override the default settings.
  - Do not commit the local configuration file.

## Settings
- Install cryptography library
- Run script FernetKeyGenerator.py to generate key 
    ```bash
    $ pip install cryptography
    $ python ConvertService/FernetKeyGenerator.py    (for ubuntu/lilux or macos)
    $ python .\ConvertService\FernetKeyGenerator.py  (for window)
    ```

- Copy this key into `P-017_ReservationConvertService/ConvertService/.env.{name}`


## Dev Environment

Start the container and launch the server.

```bash
$ chmod +x db/initdb.d/create-db.sh             (for ubuntu/lilux or macos)
$ chmod +x ConvertService/scripts/*.sh          (for ubuntu/lilux or macos)
$ docker compose -f docker-compose.yml -f dev.yml up -d
```

## Staging Environment

Start the container and launch the server.

```bash
$ chmod +x db/initdb.d/create-db.sh             (for ubuntu/lilux or macos)
$ chmod +x ConvertService/scripts/*.sh          (for ubuntu/lilux or macos)
$ docker compose -f docker-compose.yml -f staging.yml up -d
```

## Rebuild the Docker

If you need to rebuild the Docker image (e.g., after adding libraries), stop the container, remove the old image, and restart.

  - Use docker image ls to list images and find the P-017_ReservationConvertService image ID.
  - Remove the specific image using docker image rm.
```bash
$ docker compose down
$ docker image ls

    REPOSITORY               TAG               IMAGE ID       CREATED       SIZE
    arctec_convert_service   convert_service   c795199916a8   2 days ago    421MB
    mysql                    8.0               6c55ddbef969   8 weeks ago   591MB

$ docker image rmi [image_id]
```
- Remove the old volume
```bash
$ docker volume ls

    DRIVER    VOLUME NAME
    local     p-017_reservationconvertservice_db_test_volume
    local     p-017_reservationconvertservice_db_volume

$ docker volume rm -f p-017_reservationconvertservice_db_test_volume 
$ docker volume rm -f p-017_reservationconvertservice_db_volume
```
- Rebuild the Docker
```bash
$ docker compose -f docker-compose.yml -f [name].yml up -d
```

## ImportData
- If you want to add SQL for the settings, please create a new SQL file with the same format as the existing files in the path ConvertService/data.
- If the program has already started, please run the command below to import data:
```bash
$ docker ps

  CONTAINER ID   IMAGE                                           COMMAND                  CREATED       STATUS                PORTS                                                    NAMES
  ebe89a72d83a   arctec_convert_service:convert_service          "sh -c './scripts/wa…"   11 days ago   Up 6 days             0.0.0.0:16310->8000/tcp, :::16310->8000/tcp              p-017_reservationconvertservice-server-1
  4c8a37f4f5df   p-017_reservationconvertservice-celery_worker   "sh -c ./scripts/cel…"   11 days ago   Up 7 days             8000/tcp                                                 p-017_reservationconvertservice-celery_worker-1
  1e277ade61fb   redis:alpine                                    "docker-entrypoint.s…"   11 days ago   Up 7 days (healthy)   0.0.0.0:6379->6379/tcp, :::6379->6379/tcp                p-017_reservationconvertservice-redis-1
  e1674c42d9e9   mysql:8.0                                       "docker-entrypoint.s…"   11 days ago   Up 7 days             33060/tcp, 0.0.0.0:16312->3306/tcp, :::16312->3306/tcp   p-017_reservationconvertservice-db_test-1
  acd37c632490   mysql:8.0                                       "docker-entrypoint.s…"   11 days ago   Up 7 days             33060/tcp, 0.0.0.0:16311->3306/tcp, :::16311->3306/tcp   p-017_reservationconvertservice-db-1

$ docker exec -i [CONTAINER ID] python manage.py shell < ConvertService/ImportData.py
```
- Replace the CONTAINER ID of the image arctec_convert_service:convert_service with the CONTAINER ID on your machine.
- Example: 
```bash
$ docker exec -i ebe python manage.py shell < ConvertService/ImportData.py
```

- Note: Do not modify the old file after importing data; add a new sql file to proceed with importing data into the database.

## Web URL
In the development environment, access the web at the following URL. Adjust the URL for other environments based on the deployment configuration.
- Web URL: http://localhost:16310

URL availability, authentication settings, and Basic Auth parameters can be configured in the configuration file
- If you want to log in, please use the SUPERUSER_EMAIL and SUPERUSER_PASSWORD that you have previously set in P-017_ReservationConvertService/ConvertService/.env.{name}