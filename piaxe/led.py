import time
from math import ceil, fabs

def pwm(ser, r, g, b, debug=False):
     #09 00 00 00 08 10 FF 00 00
     packet = bytes([0x09, 0x00, 0x00, 0x00, 0x08, 0x10, r, g, b])
     ser.write(packet)
     if debug:
        print("ctrl tx: [%s]" % prettyHex(packet))
     
def prettyHex(data):
    return ' '.join(f'{byte:02X}' for byte in data)

def set_led(ser, r, g, b):
    # Set the LED color
    pwm(ser, r, g, b)
    time.sleep(0.1)
    

