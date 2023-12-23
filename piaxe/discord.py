import requests
import json
import logging
import time

class Alerter:
    def __init__(self, config):
        self.config = config
        self.triggered_alerts = dict()
        self.name = self.config["name"]
        self.retrigger_time = self.config["retrigger_time"]

    def alert(self, key, msg):
        raise NotImplementedError

    def alert_if(self, key, msg, cond):
        if not cond:
            if key in self.triggered_alerts:
                self.alert(key, "recovered")
                del self.triggered_alerts[key]
            return
        else:
        # check if msg in triggered alerts map
            if key in self.triggered_alerts:
                trigger_time = self.triggered_alerts[key]
                # don't trigger too often
                if (time.time() - trigger_time) < self.retrigger_time:
                    return

        if self.alert(key, msg):
            self.triggered_alerts[key] = time.time()

class DiscordWebhookAlerter(Alerter):
    def __init__(self, config):
        super().__init__(config)

        # get webhook url
        self.url = self.config["url"]

        # if it starts with file:// load content from file
        if self.url.startswith('file://'):
            file_path = self.url[7:]
            try:
                with open(file_path, 'r') as file:
                    self.url = file.read().strip()
            except FileNotFoundError:
                raise Exception(f"The file specified in the URL does not exist: {file_path}")

    def alert(self, key, msg):
        try:
            response = requests.post(self.url, data=json.dumps({"content": f"[{key}] {msg}", "username": self.name}), headers={'Content-Type': 'application/json'})
            if response.status_code != 204:
                raise Exception(response.status_code)
            #logging.debug(f"would alert {key} {msg}")
            return True
        except Exception as e:
            logging.error("alerter error: %s", e)
        return False



