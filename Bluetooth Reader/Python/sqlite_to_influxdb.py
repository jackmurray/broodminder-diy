import json
import sqlite3
import os
import time
import argparse
import influxdb_client
import influxdb_client.client.query_api
from influxdb_client.client.write_api import SYNCHRONOUS, WritePrecision
import flask
from flask import jsonify, request

UPLOAD_FOLDER = "/tmp"
TMP_FILENAME = "broodminder_upload.tmp"

# The sqlite DB stores the temp in F, so this class will convert it.
class BroodMinderResult:
    def __init__(self, deviceId, sampleNumber, timestamp, temperatureF, humidityPercent, batteryPercent, weight = None):
        self.DeviceId = deviceId
        self.SampleNumber = sampleNumber
        self.Timestamp = timestamp
        self.TemperatureF = temperatureF
        self.TemperatureC = (temperatureF - 32) * 5 / 9
        self.HumidityPercent = humidityPercent
        self.BatteryPercent = batteryPercent
        self.Weight = weight # TH devices don't have weight, so by default this will be None.
        # The MyBroodMinder API expects the temperature in F :(

class BroodMinderInfluxClient:
    def __init__(self, write_api: influxdb_client.WriteApi, query_api: influxdb_client.QueryApi, org, bucket):
        self.write_api = write_api
        self.org = org
        self.bucket = bucket
        self.query_api = query_api

    def write(self, data: BroodMinderResult):
        p = influxdb_client.Point("broodminder").tag("deviceId", data.DeviceId).field("temperature", data.TemperatureC).field(
        "humidity", data.HumidityPercent).field("battery", data.BatteryPercent).field("sampleNumber", data.SampleNumber).time(
        data.Timestamp, write_precision=WritePrecision.S)

        self.write_api.write(self.bucket, self.org, record=p)
    
    def getLatestRecord(self, deviceId: str):
        query = """from(bucket: "{0}")
                    |> range(start: -100y)
                    |> filter(fn: (r) => r["_measurement"] == "broodminder")
                    |> filter(fn: (r) => r["_field"] == "temperature")
                    |> filter(fn: (r) => r["deviceId"] == "{1}")
                    |> last()""".format(self.bucket, deviceId)
        records = self.query_api.query_stream(query)
        for r in records: # There should only be 1 result anyway
            print(r)
            return r["_time"]


# Read records from uploaded db file and send to InfluxDB. Not even slightly thread-safe.
def handle_uploaded_file(file, client: BroodMinderInfluxClient):
    # TODO: query influxdb and find the most recent record, and then only copy records later than that.
    file.save(os.path.join(UPLOAD_FOLDER, TMP_FILENAME))

    db = sqlite3.connect(os.path.join(UPLOAD_FOLDER, TMP_FILENAME))
    db.row_factory = sqlite3.Row # Enable named columns
    cur = db.cursor()
    cur.execute("SELECT * FROM StoredSensorReading")

    # TODO: group records from db by deviceId and query them from influxdb separately
    
    for row in cur:
        most_recent_record = client.getLatestRecord(row['DeviceId'])
        print(most_recent_record)
        result = BroodMinderResult(row['DeviceId'], row['Sample'], row['Timestamp'], row['Temperature'], row['Humidity'], row['Battery'])
        client.write(result)

    db.close()
    os.unlink(os.path.join(UPLOAD_FOLDER, TMP_FILENAME)) # Delete file now that we're done
    return ok('File uploaded')

def error(message, code = 400):
    resp = jsonify({'result': 'error', 'message': message})
    resp.status_code = code
    return resp

def ok(message):
    resp = jsonify({'result': 'ok', 'message': message})
    resp.status_code = 200
    return resp

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # In order to better support running in Docker, all arguments can be specified via env vars too.
    parser.add_argument("--output", help="Where to send the discovered data", default=os.environ.get("OUTPUT_MODE", "cloud"), choices=["cloud", "influxdb"])
    parser.add_argument("--influxdb-url", help="InfluxDB Server URL, needed if output=influxdb", default=os.environ.get("INFLUXDB_URL"))
    parser.add_argument("--influxdb-org", help="InfluxDB Organisation, needed if output=influxdb", default=os.environ.get("INFLUXDB_ORG"))
    parser.add_argument("--influxdb-bucket", help="InfluxDB Bucket, needed if output=influxdb", default=os.environ.get("INFLUXDB_BUCKET"))
    parser.add_argument("--influxdb-token", help="InfluxDB Auth Token, needed if output=influxdb", default=os.environ.get("INFLUXDB_TOKEN"))
    args = parser.parse_args()

    influxdb_url = getattr(args, "influxdb_url", None)
    influxdb_org = getattr(args, "influxdb_org", None)
    influxdb_bucket = getattr(args, "influxdb_bucket", None)
    influxdb_token = getattr(args, "influxdb_token", None)

    if influxdb_url is None:
        raise ValueError("influxdb-url must be set with output=influxdb")
    if influxdb_org is None:
        raise ValueError("influxdb-org must be set with output=influxdb")
    if influxdb_bucket is None:
        raise ValueError("influxdb-bucket must be set with output=influxdb")
    if influxdb_token is None:
        raise ValueError("influxdb-token must be set with output=influxdb")

    client = influxdb_client.InfluxDBClient(url=influxdb_url, token=influxdb_token, org=influxdb_org)
    influxdb_write_api = client.write_api(write_options=SYNCHRONOUS)
    influxdb_query_api = client.query_api()

    print("Starting Flask")

    app = flask.Flask(__name__)
    app.config["DEBUG"] = True

    @app.route('/', methods=['GET'])
    def home():
        return "hello flask"
    
    @app.route('/upload', methods=['POST'])
    def upload():
        # check if the post request has the file part
        if 'file' not in request.files:
            return error('No file uploaded')
        file = request.files['file']
        client = BroodMinderInfluxClient(influxdb_write_api, influxdb_query_api, influxdb_org, influxdb_bucket)
        return handle_uploaded_file(file, client)

    app.run(host='0.0.0.0')
