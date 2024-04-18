from flask import Flask, request, jsonify, send_from_directory
import threading
import logging
import random

class ASICFrequencyManager:
    def __init__(self, config, asics):
        self.app = Flask(__name__)
        self.cm = asics.clock_manager
        self.config = config

        # Define routes
        self.app.add_url_rule('/clocks', 'get', self.get_clocks, methods=['GET'])
        self.app.add_url_rule('/clock/<int:id>', 'set', self.set_clock, methods=['POST'])
        self.app.add_url_rule('/stats', 'get_stats', self.get_stats, methods=['GET'])

        # Route to serve the index.html
        self.app.add_url_rule('/', 'root', self.root)

    def root(self):
        # Serve index.html
        return send_from_directory("./manager", 'index.html')

    def get_clocks(self):
        clocks = self.cm.get_clock(-1)
        return jsonify(clocks)

    def get_stats(self):
        # Dummy data for example purposes:
        stats = {
            "hashrates": [random.randint(50, 100) for _ in range(16)],  # Random hash rates for 16 ASICs
            "voltages": [random.uniform(1.0, 1.5) for _ in range(4)]  # Random voltages for 4 domains
        }
        return jsonify(stats)

    def set_clock(self, id):
        if id < 0 or id >= self.cm.num_asics:
            return jsonify({"error": "Invalid ASIC ID"}), 400
        new_frequency = float(request.json.get('frequency'))
        if new_frequency is None or not (50.0 <= new_frequency <= 550.0):
            return jsonify({"error": f"Invalid frequency {new_frequency}"}), 400
        try:
            self.cm.set_clock(id, new_frequency)
        except Exception as e:
            logging.error(e)
            return jsonify({"error": f"Error setting clock to {new_frequency}"}), 400
        return jsonify({"success": True, "frequency": new_frequency})

    def run(self):
        host = self.config.get("host", "127.0.0.1")
        port = int(self.config.get("port", "5000"))
        def run_app():
            self.app.run(host=host, port=port, debug=True, use_reloader=False)

        self.server_thread = threading.Thread(target=run_app)
        self.server_thread.start()
