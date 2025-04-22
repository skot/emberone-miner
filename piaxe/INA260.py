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
    if debug:
        print("ctrl rx: [%s]" % prettyHex(data))
    return data[-size:]
     
def prettyHex(data):
    return ' '.join(f'{byte:02X}' for byte in data)

def read_current(ser):

    data = i2c_read_bytes(ser, 0xBB, INA260_I2CADDR_DEFAULT, INA260_REG_CURRENT, 2)
    # print("Raw Current = %02X %02X" % (data[1], data[0]))

    return (data[1] | (data[0] << 8)) * 1.25

def read_voltage(ser):

    data = i2c_read_bytes(ser, 0xCC, INA260_I2CADDR_DEFAULT, INA260_REG_BUSVOLTAGE, 2)
    # print("Raw Voltage = %02X %02X" % (data[1], data[0]))

    return (data[1] | (data[0] << 8)) * 1.25

def read_power(ser):

    data = i2c_read_bytes(ser, 0xDD, INA260_I2CADDR_DEFAULT, INA260_REG_POWER, 2)
    # print("Raw Power = %02X %02X" % (data[1], data[0]))

    return (data[1] | (data[0] << 8)) * 10

