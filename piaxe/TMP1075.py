import time
import logging
from math import ceil, fabs

TMP1075_I2CADDR_0 = 0x4A        # TMP1075 0 i2c address
TMP1075_I2CADDR_1 = 0x4B        # TMP1075 1 i2c address
TMP1075_TEMP_REG = 0x00         # Temperature register
TMP1075_CONFIG_REG = 0x01       # Configuration register
TMP1075_LOW_LIMIT = 0x02        # Low limit register
TMP1075_HIGH_LIMIT = 0x03       # High limit register
TMP1075_DEVICE_ID = 0x0F        # Device ID register

def gpio_set(ser, pin, value):
    # Construct the command to set the GPIO pin
    command = bytes([0x07, 0x00, 0x00, 0x00, 0x06, pin, value])
    ser.write(command)
    logging.debug("Sent: %s" % prettyHex(command))

def i2c_send_bytes(ser, address, register, data, debug=False):
     packet = bytes([0x09, 0x00, 0x01, 0x00, 0x05, 0x20, address, register, data])
     ser.write(packet)
     if debug:
        logging.debug("ctrl tx: [%s]" % prettyHex(packet))

def i2c_read_bytes(ser, id, address, register, size, debug=False):
    ser.reset_input_buffer()
    packet = bytes([0x09, 0x00, id, 0x00, 0x05, 0x40, address, register, size])
    ser.write(packet)
    if debug:
        logging.debug("ctrl tx: [%s]" % prettyHex(packet))
    data = ser.read(size+3)
    if data:
        bytes_read = len(data)
        if bytes_read > 0:
            if debug:
                logging.debug("ctrl rx: [%s]" % prettyHex(data))
            if data[2] != id:
                logging.error("Error: ID mismatch. Expected %02X, got %02X" % (id, data[2]))
                return None
        else:
            logging.error("No data received")
            return None
    else:
        logging.error("No data received")
        return None

    return data[-size:]
     
def prettyHex(data):
    return ' '.join(f'{byte:02X}' for byte in data)

def read_air_temperature(ser, device_index, debug=False):

    if device_index == 0:
        data = i2c_read_bytes(ser, 0xAA, TMP1075_I2CADDR_0, TMP1075_TEMP_REG, 2, debug)
    elif device_index == 1:
        data = i2c_read_bytes(ser, 0xBB, TMP1075_I2CADDR_1, TMP1075_TEMP_REG, 2, debug)
    
    if data is None:
        return None
    
    if debug:
        logging.debug("Raw Temperature = %02X %02X" % (data[0], data[1]))
    
    # TMP1075 temperature is 12-bit, left-justified in 16 bits
    # Combine bytes and shift right by 4 to get 12-bit value
    raw_temp = (data[0] << 8) | data[1]
    raw_temp = raw_temp >> 4
    
    # Convert to Celsius: each LSB = 0.0625°C
    # Handle negative temperatures (two's complement for 12-bit)
    if raw_temp & 0x800:  # Check sign bit
        raw_temp = raw_temp - 4096
    
    temp_c = raw_temp * 0.0625
    
    if debug:
        logging.debug("TMP1075[%d] Temperature: %.2f°C" % (device_index, temp_c))
    
    return temp_c
