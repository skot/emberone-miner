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
        self.best_difficulty = 0.0
        self.pool_errors = 0
        self.accepted = 0
        self.not_accepted = 0
        self.total_uptime = 0
        self.total_best_difficulty = 0.0
        # self.total_valid_shares = 0
        # self.total_invalid_shares = 0
        # self.total_accepted = 0
        # self.total_not_accepted = 0

        # this will never be changed
        self.uptime = 0

        self.lock = threading.Lock()

    def import_dict(self, data):
    #     self.best_difficulty = data.get('best_difficulty', self.best_difficulty)
        self.total_uptime = data.get('total_uptime', self.total_uptime)
        self.total_best_difficulty = data.get('total_best_difficulty', self.total_best_difficulty)
        print(json.dumps(data, indent=4))
    #     self.total_valid_shares = data.get('total_valid_shares', self.total_valid_shares)
    #     self.total_invalid_shares = data.get('total_invalid_shares', self.total_invalid_shares)
    #     self.total_accepted = data.get('total_accepted', self.total_accepted)
    #     self.total_not_accepted = data.get('total_not_accepted', self.total_not_accepted)
        logging.info("loaded total uptime: %s seconds", self.total_uptime)
        logging.info("loaded total best difficulty: %f.3", self.total_best_difficulty)
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
                    .field("uptime", int(self.stats.uptime)) \
                    .field("best_difficulty", float(self.stats.best_difficulty)) \
                    .field("total_best_difficulty", float(self.stats.total_best_difficulty)) \
                    .field("pool_errors", int(self.stats.pool_errors)) \
                    .field("accepted", int(self.stats.accepted)) \
                    .field("not_accepted", int(self.stats.not_accepted)) \
                    .field("total_uptime", int(self.stats.total_uptime)) \
                    .field("difficulty", int(self.stats.difficulty))
                    # .field("total_valid_shares", int(self.stats.total_valid_shares)) \
                    # .field("total_invalid_shares", int(self.stats.total_invalid_shares)) \
                    # .field("total_accepted", int(self.stats.total_accepted)) \
                    # .field("total_not_accepted", int(self.stats.total_not_accepted)) \

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

    def load_last_values(self):
        # Create a query to fetch the latest records
        query = f'''
            from(bucket: "piaxe")
            |> range(start: -1y)
            |> filter(fn: (r) => r["_measurement"] == "mining_stats")
            |> last()
        '''

        # Execute the query
        # better to let it raise an exception instead of resetting the total counters
        tables = self.client.query_api().query(query, org="piaxe")


        # Process the results
        last_data = dict()
        for table in tables:
            for record in table.records:
                last_data[record.get_field()] = record.get_value()

        self.stats.import_dict(last_data)



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
