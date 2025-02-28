import logging
import time


try:
    import serial
except:
    pass

from . import board

class EmberoneHardware(board.Board):

    def __init__(self, config):
        self.config = config

        self.temp_sensors = []

        # Initialize serial communication
        self.syncserial_port = serial.Serial(
            port='/dev/tty.usbmodemb310cc521',  # Update this to your serial port
            baudrate=115200,
            timeout=1
        )

        # Initialize serial communication
        self._serial_port = serial.Serial(
            port='/dev/tty.usbmodemb310cc523',  # Update this to your serial port
            baudrate=115200,
            timeout=1
        )

    def gpio_set(self, pin, value):
        # Construct the command to set the GPIO pin
        command = bytes([0x07, 0x00, 0x00, 0x00, 0x06, pin, value])
        self.syncserial_port.write(command)

    def set_fan_speed(self, channel, percent):
        pass

    def read_temperature_and_voltage(self):
        pass

    def set_led(self, state):
        pass

    def reset_func(self, state):
        self.gpio_set(0x00, 0) #ASIC RST Low
        time.sleep(0.5)
        self.gpio_set(0x00, 1) #ASIC RST High
        time.sleep(0.5)

    def shutdown(self):
        # disable buck converter
        logging.info("shutdown miner ...")
        self.gpio_set(0x01, 0) #PWR_EN Low

    def serial_port(self):
        return self._serial_port
