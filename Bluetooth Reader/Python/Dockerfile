FROM python:3
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

ENV OUTPUT_MODE influxdb

COPY sqlite_to_influxdb.py .

EXPOSE 5000
ENTRYPOINT [ "python3", "/app/sqlite_to_influxdb.py" ]
