import sqlite3
import os
import time
import argparse
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
import flask

# The sqlite DB stores the temp in F, so this class will convert it.
class BroodMinderResult:
    def __init__(self, deviceId, sampleNumber, temperatureF, humidityPercent, batteryPercent, weight = None):
        self.DeviceId = deviceId
        self.SampleNumber = sampleNumber
        self.TemperatureF = temperatureF
        self.TemperatureC = (temperatureF - 32) * 5 / 9
        self.HumidityPercent = humidityPercent
        self.BatteryPercent = batteryPercent
        self.Weight = weight # TH devices don't have weight, so by default this will be None.
        # The MyBroodMinder API expects the temperature in F :(


def sendDataToInfluxDb(write_api, org: str, bucket: str, data: BroodMinderResult):
    p = influxdb_client.Point("broodminder").tag("deviceId", data.DeviceId).field("temperature", data.TemperatureC).field(
        "humidity", data.HumidityPercent).field("battery", data.BatteryPercent).field("sampleNumber", data.SampleNumber)
    write_api.write(org=org, bucket=bucket, record=p)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # In order to better support running in Docker, all arguments can be specified via env vars too.
    parser.add_argument("--daemon", help="Run in a continuous loop, scanning for new data every 60s", action="store_true")
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

    while True:
        print("Main loop started")

        # Start flask
        # Read records from DB and send to InfluxDB.
        # TODO: query influxdb and find the most recent record, and then only copy records later than that.

        

        # If we're not running in daemon mode, break out of the loop and thus exit the program.
        if getattr(args, "daemon") == False:
            break
        # If we are in daemon mode, sleep until the next run.
        else:
            time.sleep(60)
