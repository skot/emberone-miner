import logging
import time
from math import ceil, fabs
from .. import TMP75

try:
    import serial # type: ignore
except:
    pass

from . import board

def prettyHex(data):
    return ' '.join(f'{byte:02X}' for byte in data)

class JproAditHardware(board.Board):

    def __init__(self, config):
        self.config = config
        self.chip_difficulty = self.config['chip_difficulty']

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

    def enable_ASIC(self, enable):
        command = bytes([0x07, 0x00, 0x00, 0x00, 0x06, 0x00, enable])
        self._serial_port_ctrl.write(command)  

    def set_fan_speed(self, channel, percent):
        pass

    def read_temperature_and_voltage(self):

        temp0, temp1, voltage, current, power = None, None, None, None, None
        try:
            #clear the serial buffer
            self._serial_port_ctrl.reset_input_buffer()
            #self._serial_port_ctrl.reset_output_buffer()
            # Read temperature and voltage
            temp0 = TMP75.read_temperature(self._serial_port_ctrl, 0)
            #logging.debug("temp0 = %.2f" % temp0)
            temp1 = TMP75.read_temperature(self._serial_port_ctrl, 1)
            #logging.debug("temp1 = %.2f" % temp1)
        except Exception as e:
            logging.error(f"Error reading temperature and voltage: {e}")

        return {
            "temp": [temp0, temp1, None, None],
            "voltage": [None, None, None, None],
        }

    def set_led(self, state):
        pass

    def reset_func(self):
        self.enable_ASIC(0) #ASIC RST Low
        time.sleep(0.5)
        self.enable_ASIC(1) #ASIC RST High
        time.sleep(0.5)

    def board_init(self):
        pass

    def shutdown(self):
        logging.info("shutdown miner ...")

    def serial_port(self):
        return self._serial_port_asic
