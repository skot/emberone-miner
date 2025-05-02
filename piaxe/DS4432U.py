import serial
import time
from math import ceil, fabs
import numpy as np
import logging

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

START_VOLTAGE = 2.9
INCREMENT = 0.05  # Increment for voltage ramping
INCREMENT_DELAY = 0.5  # Delay between increments in seconds

def gpio_set(ser, pin, value):
    # Construct the command to set the GPIO pin
    command = bytes([0x07, 0x00, 0x00, 0x00, 0x06, pin, value])
    ser.write(command)
    logging.debug("Sent: %s" % prettyHex(command))

def i2c_send_bytes(ser, address, register, data):
     packet = bytes([0x09, 0x00, 0x01, 0x00, 0x05, 0x20, address, register, data])
     ser.write(packet)
     logging.debug("Sent: %s" % prettyHex(packet))
     

def prettyHex(data):
    return ' '.join(f'{byte:02X}' for byte in data)

def enable_vreg(ser, enable):
    if enable:
        logging.info("Enabling voltage regulator")
    else:
        logging.info("Disabling voltage regulator")
    gpio_set(ser, 0x01, enable)
        

def _set_current_code(ser, output, code):
    reg = DS4432U_OUT0_REG if (output == 0) else DS4432U_OUT1_REG
    logging.debug("I2C Setting reg %02X to %02X" % (reg, code))
    i2c_send_bytes(ser, DS4432U_SENSOR_ADDR, reg, code)

def set_voltage(ser, vout):
    # make sure the requested voltage is in within range of BITAXE_VMIN and BITAXE_VMAX
    if (vout >= EMBER_VMAX) or (vout <= EMBER_VMIN):
        logging.error("Requested voltage is out of range")
        raise ValueError("Requested voltage is out of range")

    # this is the transfer function. comes from the DS4432U+ datasheet
    change = fabs((((LM25119_VFB / EMBER_RB) - ((vout - LM25119_VFB) / EMBER_RA)) / EMBER_IFS) * 127.0)
    code = int(ceil(change))

    # Set the MSB high if the requested voltage is BELOW nominal
    if (vout < EMBER_VNOM):
        code |= 0x80

    _set_current_code(ser, 0, code)

def ramp_voltage(ser, end):
    if START_VOLTAGE > end:
        raise ValueError("Start voltage %.2f is larger than end voltage %.2f" % (START_VOLTAGE, end))
    if end < EMBER_VMIN:
        raise ValueError("%.2f is less than EMBER_VMIN %.2f" % (end, EMBER_VMIN))

    # Ramp the voltage from start to end
    print("Setting voltage to %.2f" % START_VOLTAGE)
    set_voltage(ser, START_VOLTAGE)
    time.sleep(INCREMENT_DELAY)
    enable_vreg(ser, 1)  # Set PWR_EN GPIO pin 1 high
    time.sleep(INCREMENT_DELAY)

    for voltage in np.arange(START_VOLTAGE+INCREMENT, end, INCREMENT):
        logging.info("Setting voltage to %.2f" % voltage)
        set_voltage(ser, voltage)
        time.sleep(INCREMENT_DELAY)