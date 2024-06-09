import logging
import requests
import threading
import time
from influxdb_client import Point, WritePrecision

class Tasmota:
    def __init__(self, config):
        self.url = config['url']
        self.data_lock = threading.Lock()
        self.latest_data = None
        self.fetch_thread = threading.Thread(target=self._fetch_data_loop)
        self.shutdown_event = threading.Event()

    def _fetch_data_loop(self):
        """Thread loop for fetching data."""
        logging.info("smartplug monitoring started ...")
        while not self.shutdown_event.is_set():
            try:
                response = requests.get(self.url, timeout=5)
                response.raise_for_status()  # will raise an exception for 4XX/5XX errors
                with self.data_lock:
                    self.latest_data = response.json()
            except Exception as e:
                logging.error("Failed to fetch data from smart plug: %s", e)
                with self.data_lock:
                    self.latest_data = None
            time.sleep(5)

    def start(self):
        """Start the fetch thread."""
        self.fetch_thread.start()

    def shutdown(self):
        """Shutdown fetch thread and wait for it to finish."""
        self.shutdown_event.set()
        self.fetch_thread.join()

    def add_smart_plug_energy_data(self, point):
        """Fetch latest data and add to point, if available."""
        with self.data_lock:
            if self.latest_data is None:
                return

            data = self.latest_data
            energy_data = data["StatusSNS"]["ENERGY"]
            point.field("temperature_sp", float(data["StatusSNS"]["ANALOG"]["Temperature"])) \
                .field("power", float(energy_data["Power"])) \
                .field("apparent_power", float(energy_data["ApparentPower"])) \
                .field("reactive_power", float(energy_data["ReactivePower"])) \
                .field("factor", float(energy_data["Factor"])) \
                .field("voltage", float(energy_data["Voltage"])) \
                .field("current", float(energy_data["Current"])) \
                .field("total_consumption", float(energy_data["Total"]))