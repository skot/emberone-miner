import time
from math import ceil, fabs

INA260_I2CADDR_DEFAULT      = 0x40 # INA260 default i2c address
INA260_REG_CONFIG           = 0x00 # Configuration register
INA260_REG_CURRENT          = 0x01 # Current measurement register (signed) in mA
INA260_REG_BUSVOLTAGE       = 0x02 # Bus voltage measurement register in mV
INA260_REG_POWER            = 0x03 # Power calculation register in mW
INA260_REG_MASK_ENABLE      = 0x06 # Interrupt/Alert setting and checking register
INA260_REG_ALERT_LIMIT      = 0x07 # Alert limit value register
INA260_REG_MFG_UID          = 0xFE # Manufacturer ID Register
INA260_REG_DIE_UID          = 0xFF # Die ID and Revision Register

INA260_TIME_140_us = 0   # Measurement time: 140us
INA260_TIME_204_us = 1   # Measurement time: 204us
INA260_TIME_332_us = 2   # Measurement time: 332us
INA260_TIME_558_us = 3   # Measurement time: 558us
INA260_TIME_1_1_ms = 4   # Measurement time: 1.1ms (Default)
INA260_TIME_2_116_ms = 5 # Measurement time: 2.116ms
INA260_TIME_4_156_ms = 6 # Measurement time: 4.156ms
INA260_TIME_8_244_ms = 7 # Measurement time: 8.224ms

INA260_COUNT_1 = 0    # Window size: 1 sample (Default)
INA260_COUNT_4 = 1    # Window size: 4 samples
INA260_COUNT_16 = 2   # Window size: 16 samples
INA260_COUNT_64 = 3   # Window size: 64 samples
INA260_COUNT_128 = 4  # Window size: 128 samples
INA260_COUNT_256 = 5  # Window size: 256 samples
INA260_COUNT_512 = 6  # Window size: 512 samples
INA260_COUNT_1024 = 7 # Window size: 1024 samples


INA260_CURRENT_FACTOR = 1.25 # Current factor in mA/LSB
INA260_VOLTAGE_FACTOR = 1.25 # Voltage factor in mV/LSB
INA260_POWER_FACTOR = 10 # Power factor in mW/LSB

def gpio_set(ser, pin, value):
    # Construct the command to set the GPIO pin
    command = bytes([0x07, 0x00, 0x00, 0x00, 0x06, pin, value])
    ser.write(command)
    print("Sent: %s" % prettyHex(command))

def i2c_send_bytes(ser, address, register, data, len, debug=False):
    packet = bytes([0x08+len, 0x00, 0x01, 0x00, 0x05, 0x20, address, register] + data)
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

def init(ser):
    # Configure the INA260
    config_setting = (INA260_TIME_1_1_ms << 3) | (INA260_TIME_1_1_ms << 6) | (INA260_COUNT_128 << 9)
    i2c_send_bytes(ser, INA260_I2CADDR_DEFAULT, INA260_REG_CONFIG, [((config_setting >> 8) & 0xFF), (config_setting & 0xFF)], 2, True)
    time.sleep(0.1)

def read_current(ser):

    data = i2c_read_bytes(ser, 0xBB, INA260_I2CADDR_DEFAULT, INA260_REG_CURRENT, 2, True)
    # print("Raw Current = %02X %02X" % (data[1], data[0]))

    return (data[1] | (data[0] << 8)) * INA260_CURRENT_FACTOR

def read_voltage(ser):

    data = i2c_read_bytes(ser, 0xCC, INA260_I2CADDR_DEFAULT, INA260_REG_BUSVOLTAGE, 2, True)
    # print("Raw Voltage = %02X %02X" % (data[1], data[0]))

    return (data[1] | (data[0] << 8)) * INA260_VOLTAGE_FACTOR

def read_power(ser):

    data = i2c_read_bytes(ser, 0xDD, INA260_I2CADDR_DEFAULT, INA260_REG_POWER, 2, True)
    # print("Raw Power = %02X %02X" % (data[1], data[0]))

    return (data[1] | (data[0] << 8)) * INA260_POWER_FACTOR

