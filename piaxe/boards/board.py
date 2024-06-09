class Board:
    def set_fan_speed(self, channel, speed):
        raise NotImplementedError

    def read_temperature(self):
        raise NotImplementedError

    def set_led(self, state):
        raise NotImplementedError

    def reset_func(self, state):
        raise NotImplementedError

    def shutdown(self):
        raise NotImplementedError

    def serial_port(self):
        raise NotImplementedError

    def get_asic_frequency(self):
        return self.config['asic_frequency']

    def get_name(self):
        return self.config['name']

    def get_chip_count(self):
        return self.config['chips']