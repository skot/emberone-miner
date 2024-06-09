# piaxe
import logging
import serial
import time

try:
    import RPi.GPIO as GPIO
    from rpi_hardware_pwm import HardwarePWM
    import smbus
except:
    pass

from . import board

class RPiHardware(board.Board):
    def __init__(self, config):
        # Setup GPIO
        GPIO.setmode(GPIO.BOARD)  # Use Physical pin numbering

        # Load settings from config
        self.config = config
        self.sdn_pin = self.config['sdn_pin']
        self.pgood_pin = self.config['pgood_pin']
        self.nrst_pin = self.config['nrst_pin']
        self.led_pin = self.config['led_pin']
        self.lm75_address = self.config['lm75_address']

        # Initialize GPIO Pins
        GPIO.setup(self.sdn_pin, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.pgood_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.nrst_pin, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setup(self.led_pin, GPIO.OUT, initial=GPIO.LOW)

        # Create an SMBus instance
        self._bus = smbus.SMBus(1)  # 1 indicates /dev/i2c-1

        pwm = HardwarePWM(pwm_channel=0, hz=self.config['pwm_hz'])
        pwm.start(self.config['pwm_duty_cycle'])

        # Initialize serial communication
        self._serial_port = serial.Serial(
            port=self.config['serial_port'],  # For GPIO serial communication use /dev/ttyS0
            baudrate=115200,    # Set baud rate to 115200
            bytesize=serial.EIGHTBITS,     # Number of data bits
            parity=serial.PARITY_NONE,     # No parity
            stopbits=serial.STOPBITS_ONE,  # Number of stop bits
            timeout=1                      # Set a read timeout
        )

        GPIO.output(self.sdn_pin, True)

        while (not self._is_power_good()):
            print("power not good ... waiting ...")
            time.sleep(1)

    def _is_power_good(self):
        return GPIO.input(self.pgood_pin)

    def set_fan_speed(self, channel, speed):
        pass

    def read_temperature_and_voltage(self):
        data = self._bus.read_i2c_block_data(self.lm75_address, 0, 2)
        # Convert the data to 12-bits
        temp = (data[0] << 4) | (data[1] >> 4)
        # Convert to a signed 12-bit value
        if temp > 2047:
            temp -= 4096

        # Convert to Celsius
        celsius = temp * 0.0625
        return {
            "temp": [celsius, None, None, None],
            "voltage": [None, None, None, None],
        }

    def set_led(self, state):
        GPIO.output(self.led_pin, True if state else False)

    def reset_func(self):
        GPIO.output(self.nrst_pin, True)
        time.sleep(0.5)
        GPIO.output(self.nrst_pin, False)
        time.sleep(0.5)


    def shutdown(self):
        # disable buck converter
        logging.info("shutdown miner ...")
        GPIO.output(self.sdn_pin, False)
        self.set_led(False)

    def serial_port(self):
        return self._serial_port