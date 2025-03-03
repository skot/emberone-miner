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

        # Initialize serial communication
        self._serial_port_asic = serial.Serial(
            port=self.config['serial_port_asic'],  # For ASIC serial communication use usbmodemb310cc523
            baudrate=115200,    # Set baud rate to 115200
            bytesize=serial.EIGHTBITS,     # Number of data bits
            parity=serial.PARITY_NONE,     # No parity
            stopbits=serial.STOPBITS_ONE,  # Number of stop bits
            timeout=1                      # Set a read timeout
        )

        # Initialize serial communication
        self._serial_port_ctrl = serial.Serial(
            port=self.config['serial_port_ctrl'],  # For GPIO serial communication use usbmodemb310cc521
            baudrate=115200,    # Set baud rate to 115200
            bytesize=serial.EIGHTBITS,     # Number of data bits
            parity=serial.PARITY_NONE,     # No parity
            stopbits=serial.STOPBITS_ONE,  # Number of stop bits
            timeout=1                      # Set a read timeout
        )

    def gpio_set(self, pin, value):
        # Construct the command to set the GPIO pin
        command = bytes([0x07, 0x00, 0x00, 0x00, 0x06, pin, value])
        self._serial_port_ctrl.write(command)

    def set_fan_speed(self, channel, percent):
        pass

    def read_temperature_and_voltage(self):
        return {
            "temp": [None, None, None, None],
            "voltage": [None, None, None, None],
        }

    def set_led(self, state):
        pass

    def reset_func(self):
        self.gpio_set(0x00, 0) #ASIC RST Low
        time.sleep(0.5)
        self.gpio_set(0x00, 1) #ASIC RST High
        time.sleep(0.5)

    def shutdown(self):
        # disable buck converter
        logging.info("shutdown miner ...")
        self.gpio_set(0x01, 0) #PWR_EN Low

    def serial_port(self):
        return self._serial_port_asic
