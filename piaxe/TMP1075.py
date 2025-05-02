import time
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
    print("Sent: %s" % prettyHex(command))

def i2c_send_bytes(ser, address, register, data, debug=False):
     packet = bytes([0x09, 0x00, 0x01, 0x00, 0x05, 0x20, address, register, data])
     ser.write(packet)
     if debug:
        print("ctrl tx: [%s]" % prettyHex(packet))

def i2c_read_bytes(ser, id, address, register, size, debug=False):
    ser.reset_input_buffer()
    packet = bytes([0x09, 0x00, id, 0x00, 0x05, 0x40, address, register, size])
    ser.write(packet)
    if debug:
        print("ctrl tx: [%s]" % prettyHex(packet))
    data = ser.read(size+3)
    if data:
        bytes_read = len(data)
        if bytes_read > 0:
            if debug:
                print("ctrl rx: [%s]" % prettyHex(data))
            if data[2] != id:
                print("Error: ID mismatch. Expected %02X, got %02X" % (id, data[2]))
                return None
        else:
            print("No data received")
            return None
    else:
        print("No data received")
        return None

    return data[-size:]
     
def prettyHex(data):
    return ' '.join(f'{byte:02X}' for byte in data)

def read_temperature(ser, device_index):

    if device_index == 0:
        data = i2c_read_bytes(ser, 0xAA, TMP1075_I2CADDR_0, TMP1075_TEMP_REG, 2)
    elif device_index == 1:
        data = i2c_read_bytes(ser, 0xBB, TMP1075_I2CADDR_1, TMP1075_TEMP_REG, 2)
    # print("Raw Temperature = %02X %02X" % (data[0], data[1]))
    # print("Temperature[%d] = %d" % (device_index, data[0]))
    
    return data[0]
