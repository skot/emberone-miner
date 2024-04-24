import serial
import threading
import time

from . import flex4axe

try:
    from . import coms_pb2
    import binascii
except:
    pass

class ZeroxAxe(flex4axe.Flex4AxeHardware):
    def __init__(self, config):
        super().__init__(config)

    def read_temperature_and_voltage(self):
        data = super().read_temperature_and_voltage()
        # for simpler board layout the voltage domains are reversed but the firmware is the
        # same as the flex4 to not have another firmware
        data['voltage'].reverse()

        for i in range(0, 4):
            # don't ask ... :weird-smiley-guy:
            data['voltage'][i] *= 1.02568560

        return data