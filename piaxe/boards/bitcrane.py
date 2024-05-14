import logging
import time


try:
    import pyftdi.serialext
    from pyftdi.gpio import GpioSyncController
    from pyftdi.i2c import I2cController, I2cIOError
except:
    pass

from . import board

class BitcraneHardware(board.Board):
    TMP75_ADDRESSES = [ 0x48, 0x4C ]
    EMC2305_ADDRESS = 0x4D
    FAN_PWM_REGISTERS = [0x30, 0x40, 0x50, 0x60, 0x70]

    def __init__(self, config):
        self.config = config

        i2c = I2cController()
        i2c.configure('ftdi://ftdi:4232/2',
                      frequency=100000,
                      clockstretching=False,
                      debug=True)
        self.rst_plug_gpio = i2c.get_gpio()
        self.rst_plug_gpio.set_direction(0x30, 0x30)
        self.temp_sensors = []
        for address in BitcraneHardware.TMP75_ADDRESSES:
            self.temp_sensors.append(i2c.get_port(address))

        self.fan_controller = i2c.get_port(BitcraneHardware.EMC2305_ADDRESS)

        # Initialize serial communication
        self._serial_port = pyftdi.serialext.serial_for_url('ftdi://ftdi:4232/1',
                                                            baudrate=115200,
                                                            timeout=1)

        self.set_fan_speed(0, config['fan_speed'])

    def set_fan_speed(self, channel, percent):
        pwm_value = int(255 * percent)
        for fan_reg in BitcraneHardware.FAN_PWM_REGISTERS:
            self.fan_controller.write_to(fan_reg, [pwm_value])
        print(f"Set fan to {percent * 100}% speed.")

    def read_temperature_and_voltage(self):
        highest_temp = 0
        for sensor in self.temp_sensors:
            temp = sensor.read_from(0x00, 2)
            if highest_temp < temp[0]:
                highest_temp = temp[0]

        return {
            "temp": [highest_temp + 5, None, None, None],
            "voltage": [None, None, None, None],
        }

    def set_led(self, state):
        pass

    def reset_func(self, state):
        self.rst_plug_gpio.write(0x00)
        time.sleep(0.5)
        self.rst_plug_gpio.write(0x30)
        time.sleep(0.5)

    def shutdown(self):
        # disable buck converter
        logging.info("shutdown miner ...")
        self.reset_func(True)

    def serial_port(self):
        return self._serial_port
