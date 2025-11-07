import time
import logging
import struct
from math import ceil, fabs

TMP75_I2CADDR0 = 0x4C        # TMP75 I2C address (0x4C and 0x48 on S19j Pro)
TMP75_I2CADDR1 = 0x48        # TMP75 I2C address (0x4C and 0x48 on S19j Pro)
TMP75_TEMP_REG = 0x00       # Temperature register (read 12 bits)
TMP75_CONFIG_REG = 0x01     # Configuration register (defaults to 0x00)
TMP75_TLO_REG = 0x02        # Temperature low limit register
TMP75_THI_REG = 0x03        # Temperature high limit register


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

def read_temperature(ser, chipnum=0):

    if chipnum == 0:
        address = TMP75_I2CADDR0
    else:
        address = TMP75_I2CADDR1

    data = i2c_read_bytes(ser, 0xBB, address, TMP75_TEMP_REG, 2)

    logging.debug("Raw Temperature = %02X %02X" % (data[0], data[1]))
    # convert data to signed 12 bit integer with struct
    temp = (struct.unpack('>h', data)[0] >> 4) / 16.0
    logging.debug("Temperature = %.2f" % temp)

    return temp

def read_config(ser, chipnum=0):

    if chipnum == 0:
        address = TMP75_I2CADDR0
    else:
        address = TMP75_I2CADDR1

    data = i2c_read_bytes(ser, 0xCC, address, TMP75_CONFIG_REG, 1)[0]

    logging.debug("Config Register = %02X" % data)

    return data
