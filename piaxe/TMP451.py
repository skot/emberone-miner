import time
import logging
from math import ceil, fabs

TMP451_I2CADDR = 0x49        # TMP451 I2C address
TMP451_LOCAL_TEMP_HI = 0x00    # Local Temperature register, High byte
TMP451_LOCAL_TEMP_LO = 0x15    # Local Temperature register, Low byte
TMP451_REMOTE_TEMP_HI = 0x01   # Remote Temperature register, High byte
TMP451_REMOTE_TEMP_LO = 0x10   # Remote Temperature register, Low byte

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

def read_temperature(ser):

    data_lo = i2c_read_bytes(ser, 0xBB, TMP451_I2CADDR, TMP451_LOCAL_TEMP_LO, 1)[0]
    data_hi = i2c_read_bytes(ser, 0xAA, TMP451_I2CADDR, TMP451_LOCAL_TEMP_HI, 1)[0]

    logging.debug("Raw Temperature = %02X %02X" % (data_lo, data_hi))
    temp = data_hi + (data_lo / 256.0)
    # logging.debug("Temperature = %.2f" % temp)

    return temp
