# P-017_ReservationConvertService


## Quick initialization

- Rename `.env.example ->.env`
- Rename `ConvertService/.env.example ->.env.stg`
- Run command in terminal: 
  ```bash
  $ docker compose -f docker-compose.yml -f staging.yml up -d
  ```
## Import data
- If you want to add SQL for the settings, please create a new SQL file with the same format as the existing files in the path `ConvertService/data`.
- If the program has already started, please run the command below to import data:
  ```bash
  $ docker ps
  
    CONTAINER ID   IMAGE                                           COMMAND                  CREATED       STATUS                PORTS                                                    NAMES
    ebe89a72d83a   arctec_convert_service:convert_service          "sh -c './scripts/wa…"   11 days ago   Up 6 days             0.0.0.0:16310->8000/tcp, :::16310->8000/tcp              p-017_reservationconvertservice-server-1
    4c8a37f4f5df   p-017_reservationconvertservice-celery_worker   "sh -c ./scripts/cel…"   11 days ago   Up 7 days             8000/tcp                                                 p-017_reservationconvertservice-celery_worker-1
    1e277ade61fb   redis:alpine                                    "docker-entrypoint.s…"   11 days ago   Up 7 days (healthy)   0.0.0.0:6379->6379/tcp, :::6379->6379/tcp                p-017_reservationconvertservice-redis-1
    acd37c632490   mysql:8.0                                       "docker-entrypoint.s…"   11 days ago   Up 7 days             33060/tcp, 0.0.0.0:16311->3306/tcp, :::16311->3306/tcp   p-017_reservationconvertservice-db-1
  
  $ docker exec -i [CONTAINER ID] python manage.py shell < ConvertService/ImportData.py
  ```
- Replace the `CONTAINER ID` of the image `arctec_convert_service:convert_service` with the `CONTAINER ID` on your machine.
- Example: 
  ```bash
  $ docker exec -i ebe python manage.py shell < ConvertService/ImportData.py
  ```

- Note: Do not modify the old file after importing data; add a new sql file to proceed with importing data into the database.

## Web URL
In the development environment, access the web at the following URL. Adjust the URL for other environments based on the deployment configuration.
- Web URL: http://localhost:16310

URL availability, authentication settings, and Basic Auth parameters can be configured in the configuration file
- If you want to log in, please use the SUPERUSER_EMAIL and SUPERUSER_PASSWORD that you have previously set in ConvertService/.env.stg