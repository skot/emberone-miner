from influxdb_client import Point
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client import InfluxDBClient, Point, WriteOptions, WritePrecision
from datetime import datetime
import pytz
import logging
import threading
import json
import time

class Stats:
    def __init__(self):
        self.temp = 25.0
        self.hashing_speed = 0.0
        self.invalid_shares = 0
        self.valid_shares = 0
        self.difficulty = 512

        # this will never be changed
        self.started_at = time.time()

        self.lock = threading.Lock()


class Influx:
    def __init__(self):
        # InfluxDB settings (replace with your own settings)
        self.host = 'localhost'
        self.port = 8086
        self.token = 'f37fh783hf8hq'
        self.org = 'piaxe'
        self.bucket = 'piaxe'
        self.client = None
        self.tz = pytz.timezone('Europe/Berlin')
        self.stats = Stats()

        self.submit_thread = threading.Thread(target=self._submit_thread)
        self.submit_thread.start()


    def _submit_thread(self):
        while True:
            if not self.client:
                logging.error("no influx client")
                time.sleep(10)
                continue

            with self.stats.lock:
                point = Point("mining_stats").time(datetime.now(self.tz), WritePrecision.NS) \
                    .field("temperature", float(self.stats.temp)) \
                    .field("hashing_speed", float(self.stats.hashing_speed)) \
                    .field("invalid_shares", int(self.stats.invalid_shares)) \
                    .field("valid_shares", int(self.stats.valid_shares)) \
                    .field("uptime", int(time.time() - self.stats.started_at)) \
                    .field("difficulty", int(self.stats.difficulty))

            try:
                write_api = self.client.write_api(write_options=SYNCHRONOUS)
                write_api.write(bucket=self.bucket, org=self.org, record=point)
                logging.debug("influx data written: %s", point.to_line_protocol())
            except Exception as e:
                logging.error("writing to influx failed: %s", e)

            time.sleep(5)

    def connect(self):
        # Connect to InfluxDB
        try:
            self.client = InfluxDBClient(url=f"http://{self.host}:{self.port}", token=self.token, org=self.org)
        except Exception as e:
            logging.error("connecting influx failed: %s", e)


    def _submit_data(self, stats: Stats):
        # Timezone - Berlin

        with stats:
            # Data structure
            data = [
                {
                    "measurement": "mining_stats",
                    "time": datetime.now(self.tz).isoformat(),
                    "fields": {
                        "temperature": float(stats.temp),
                        "hashing_speed": float(stats.hashing_speed),
                        "invalid_shares": int(stats.invalid_shares),
                        "difficulty": int(stats.difficulty)
                    }
                }
            ]

        if not self.client:
            logging.error("no influx client")
            return

        # Write data
        try:
            self.client.write_points(data)
        except Exception as e:
            logging.error("writing to influx failed: %s", e)

    def close(self):
        # Close the connection
        if self.client:
            self.client.close()
