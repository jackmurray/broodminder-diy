FROM python:3

RUN pip install urllib3
RUN pip install bluepy
# RUN pip install influxdb # TODO: confirm package name

COPY BM_Scan.py /app.py

ENTRYPOINT [ "/app.py" ]
