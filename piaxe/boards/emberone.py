import logging
import time
from math import ceil, fabs

try:
    import serial # type: ignore
except:
    pass

from . import board

# DS4432U+ -- Adjustable current DAC
DS4432U_SENSOR_ADDR = 0x48  # Slave address of the DS4432U+
DS4432U_OUT0_REG = 0xF8     # register for current output 0
DS4432U_OUT1_REG = 0xF9     # register for current output 1

# DS4432U Transfer function constants for Bitaxe board
DS4432U_VRFS = 0.997        # Vrfs on DS4432U+ datasheet
EMBER_RFS = 39000.0         # R11 on emberOne/00 v2
EMBER_IFS = (DS4432U_VRFS / EMBER_RFS) * (127.0/16.0)
EMBER_RA = 3570.0           # R6 on emberOne/00 v2
EMBER_RB = 1020.0           # R7 on emberOne/00 v2
LM25119_VFB = 0.8

# EMBER_VNOM = 3.6          # this is with the current DAC set to 0. Should be pretty close to (VFB*(RA+RB))/RB
EMBER_VNOM = (LM25119_VFB * (EMBER_RA + EMBER_RB)) / EMBER_RB
EMBER_VMAX = 4.324
EMBER_VMIN = 2.875

def prettyHex(data):
    return ' '.join(f'{byte:02X}' for byte in data)
  

def DS4432U_set_voltage(vout):
    # make sure the requested voltage is in within range of BITAXE_VMIN and BITAXE_VMAX
    if (vout >= EMBER_VMAX) or (vout <= EMBER_VMIN):
        print("Requested voltage is out of range")
        return

    # this is the transfer function. comes from the DS4432U+ datasheet
    change = fabs((((LM25119_VFB / EMBER_RB) - ((vout - LM25119_VFB) / EMBER_RA)) / EMBER_IFS) * 127.0)
    code = int(ceil(change))

    # Set the MSB high if the requested voltage is BELOW nominal
    if (vout < EMBER_VNOM):
        code |= 0x80

    return code

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

    def i2c_send_bytes(self, address, register, data):
        packet = bytes([0x09, 0x00, 0x01, 0x00, 0x05, 0x20, address, register, data])
        self._serial_port_ctrl.write(packet)
        print("Sent: %s" % prettyHex(packet))

    def DS4432U_set_current_code(self, output, code):
        reg = DS4432U_OUT0_REG if (output == 0) else DS4432U_OUT1_REG
        print("I2C Setting reg %02X to %02X" % (reg, code))
        self.i2c_send_bytes(DS4432U_SENSOR_ADDR, reg, code)

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

    def board_init(self):
        DS4432U_set_voltage(value)
        time.sleep(0.1)
        self.gpio_set(0x01, 1)  # Set PWR_EN GPIO pin 1 high

    def shutdown(self):
        # disable buck converter
        logging.info("shutdown miner ...")
        self.gpio_set(0x01, 0) #PWR_EN Low

    def serial_port(self):
        return self._serial_port_asic
