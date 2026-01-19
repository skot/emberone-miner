import time
import logging
from math import ceil, fabs

TMP451_I2CADDR = 0x49        # TMP451 I2C address
TMP451_LOCAL_TEMP_HI = 0x00    # Local Temperature register, High byte
TMP451_REMOTE_TEMP_HI = 0x01   # Remote Temperature register, High byte
TMP451_STATUS = 0x02           # Status register
TMP451_REMOTE_TEMP_LO = 0x10   # Remote Temperature register, Low byte
TMP451_LOCAL_TEMP_LO = 0x15    # Local Temperature register, Low byte

# Status register bit masks
TMP451_STATUS_BUSY = 0x80      # Bit 7: ADC busy
TMP451_STATUS_LHIGH = 0x40     # Bit 6: Local high temp alarm
TMP451_STATUS_LLOW = 0x20      # Bit 5: Local low temp alarm
TMP451_STATUS_RHIGH = 0x10     # Bit 4: Remote high temp alarm
TMP451_STATUS_RLOW = 0x08      # Bit 3: Remote low temp alarm
TMP451_STATUS_OPEN = 0x04      # Bit 2: Remote diode open/fault

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

def read_air_temperature(ser, debug=False):
    """Read local temperature from TMP451 and return in degrees Celsius."""
    
    temp_lo = i2c_read_bytes(ser, 0xBB, TMP451_I2CADDR, TMP451_LOCAL_TEMP_LO, 1, debug)
    temp_hi = i2c_read_bytes(ser, 0xAA, TMP451_I2CADDR, TMP451_LOCAL_TEMP_HI, 1, debug)

    if temp_lo is None or temp_hi is None:
        return None

    if debug:
        logging.debug("Raw Temperature = %02X %02X" % (temp_hi[0], temp_lo[0]))

    # TMP451: High byte is integer part (signed), low byte upper 4 bits are fractional (0.0625°C per bit)
    # Temperature range is -40°C to +127°C
    integer_part = temp_hi[0]
    if integer_part & 0x80:  # Handle negative temperatures (two's complement)
        integer_part = integer_part - 256
    
    fractional_part = (temp_lo[0] >> 4) * 0.0625
    
    temp_c = integer_part + fractional_part

    if debug:
        logging.debug("Temperature = %.2f°C" % temp_c)

    return temp_c

def read_chip_temperature(ser, debug=False):
    """Read remote temperature from TMP451 and return in degrees Celsius.
    Returns None if the remote diode is open/fault or on read error."""
    
    # First check status register for OPEN fault
    status = i2c_read_bytes(ser, 0xCC, TMP451_I2CADDR, TMP451_STATUS, 1, debug)
    if status is not None and (status[0] & TMP451_STATUS_OPEN):
        logging.warning("TMP451 remote diode open/fault detected")
        return None
    
    temp_lo = i2c_read_bytes(ser, 0xBB, TMP451_I2CADDR, TMP451_REMOTE_TEMP_LO, 1, debug)
    temp_hi = i2c_read_bytes(ser, 0xAA, TMP451_I2CADDR, TMP451_REMOTE_TEMP_HI, 1, debug)

    if temp_lo is None or temp_hi is None:
        return None

    if debug:
        logging.debug("Raw Remote Temperature = %02X %02X" % (temp_hi[0], temp_lo[0]))

    # TMP451: High byte is integer part (signed), low byte upper 4 bits are fractional (0.0625°C per bit)
    # Temperature range is -40°C to +127°C
    integer_part = temp_hi[0]
    if integer_part & 0x80:  # Handle negative temperatures (two's complement)
        integer_part = integer_part - 256
    
    fractional_part = (temp_lo[0] >> 4) * 0.0625
    
    temp_c = integer_part + fractional_part

    if debug:
        logging.debug("Remote Temperature = %.2f°C" % temp_c)

    return temp_c

