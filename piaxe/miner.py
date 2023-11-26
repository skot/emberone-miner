import RPi.GPIO as GPIO
import serial
import time
import logging
from collections import deque
import random

from rpi_hardware_pwm import HardwarePWM

import threading
import struct
import binascii
from shared import shared

from . import bm1366
from . import utils
from . import crc_functions

SDN_PIN = 11  # SDN, output, initial high
PGOOD_PIN = 13  # PGOOD, input, floating
NRST_PIN = 15  # NRST, output, initial high
PWM_PIN = 12  # PWM output on Pin 12

class Job(shared.Job):
    def __init__(
        self,
        job_id,
        prevhash,
        coinb1,
        coinb2,
        merkle_branches,
        version,
        nbits,
        ntime,
        extranonce1,
        extranonce2_size,
        max_nonce=0x7fffffff,
    ):
        super().__init__(job_id, prevhash, coinb1, coinb2, merkle_branches, version, nbits, ntime, extranonce1, extranonce2_size, max_nonce)

class BM1366Miner:
    def __init__(self):
        self.current_job = None
        self.current_work = None
        self.serial_port = None

        self._read_index = 0
        self._write_index = 0
        self._buffer = bytearray([0] * 64)


        self.job_thread = None
        self.job_lock = threading.Lock()
        self.serial_lock = threading.Lock()
        self.stop_event = threading.Event()


    def init(self):
        # Setup GPIO
        GPIO.setmode(GPIO.BOARD)  # Use Physical pin numbering

        # Initialize GPIO Pins
        GPIO.setup(SDN_PIN, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(PGOOD_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Default is floating
        GPIO.setup(NRST_PIN, GPIO.OUT, initial=GPIO.HIGH)

        pwm = HardwarePWM(pwm_channel=0, hz=1000)
        pwm.start(80) # full duty cycle

        # Initialize serial communication
        self.serial_port = serial.Serial(
            port="/dev/ttyS0",  # For GPIO serial communication use /dev/ttyS0
            baudrate=115200,    # Set baud rate to 115200
            bytesize=serial.EIGHTBITS,    # Number of data bits
            parity=serial.PARITY_NONE,    # No parity
            stopbits=serial.STOPBITS_ONE, # Number of stop bits
            timeout=1                     # Set a read timeout
        )

        GPIO.output(SDN_PIN, True)

        while (not self._is_power_good()):
            print("power not good ... waiting ...")
            time.sleep(5)

        # set the hardware dependent functions for serial and reset
        bm1366.ll_init(self._serial_tx_func, self._serial_rx_func, self._reset_func)

        # init bm1366
        bm1366.init(485)
        init_response = bm1366.receive_work()

        if init_response.nonce != 0x00006613:
            raise Exception("bm1366 not detected")

        self.set_difficulty(512)

    def _serial_tx_func(self, data, debug=False):
        with self.serial_lock:
            total_sent = 0
            while total_sent < len(data):
                sent = self.serial_port.write(data[total_sent:])
                if sent == 0:
                    raise RuntimeError("Serial connection broken")
                total_sent += sent
            logging.debug("-> %s", bytearray(data).hex())

    def _serial_rx_func(self, size, timeout_ms, debug=False):
        self.serial_port.timeout = timeout_ms / 1000.0

        data = self.serial_port.read(size)
        bytes_read = len(data)

        if bytes_read > 0:
#            logging.debug("serial_rx: %d", bytes_read)
#            logging.debug("<- %s", data.hex())
            return data

        return None

    def _reset_func(self):
        GPIO.output(NRST_PIN, True)
        time.sleep(0.5)
        GPIO.output(NRST_PIN, False)
        time.sleep(0.5)

    def _is_power_good(self):
        return GPIO.input(PGOOD_PIN)


    def hashrate(self):
        pass # TODO

    def _set_target(self, target):
        self._target = '%064x' % target

    def set_difficulty(self, difficulty):
        self._difficulty = difficulty
        self._set_target(shared.calculate_target(difficulty))
        bm1366.set_job_difficulty_mask(difficulty)

    def set_submit_callback(self, cb):
        self.submit_cb = cb

    def _receive(self):
        while True:
            if self.stop_event.is_set():
                return

            byte = self._serial_rx_func(1, 100, debug=False)

            if not byte:
                continue

            self._buffer[self._write_index % 64] = byte[0]
            self._write_index += 1

            if self._write_index - self._read_index >= 11 and self._buffer[self._read_index % 64] == 0xaa and self._buffer[(self._read_index + 1) % 64] == 0x55:
                data = bytearray([0] * 11)
                for i in range(0, 11):
                    data[i] = self._buffer[self._read_index % 64]
                    self._read_index += 1

                logging.debug("<- %s", bytes(data).hex())

                asic_result = bm1366.AsicResult().from_bytes(bytes(data))
                if asic_result and asic_result.nonce and asic_result.nonce not in [0x0, 0x6613]:
                    with self.job_lock:
                        result = dict(
                            job_id = self.current_job._job_id,
                            extranonce2 = self.current_job._extranonce2,
                            ntime = self.current_job._ntime,
                            nonce = shared.int_to_hex32(asic_result.nonce),
                            version = shared.int_to_hex32(bm1366.reverse_uint16(asic_result.version) << 13),
                        )
                        if not shared.verify_work(self._difficulty, self.current_job, result):
                            logging.error("invalid result!")

                        self.submit_cb(result)

                    # restart miner with new extranonce2
                    self._start_with_random_extranonce2(self.current_job)



    def _start_with_random_extranonce2(self, job):
        with self.job_lock:
            extranonce2 = random.randint(0, 2**31-1)
            logging.debug("new extranonce2 %08x", extranonce2)
            job.set_extranonce2(extranonce2)

            self.current_job = job

            work = bm1366.WorkRequest()
            work.create_work(
                shared.hex_to_int(job._job_id),
                0x00000000,
                shared.hex_to_int(job._nbits),
                shared.hex_to_int(job._ntime),
                shared.reverse_bytes(shared.hex_to_bytes(job._merkle_root)),
                shared.reverse_bytes(shared.hex_to_bytes(job._prevhash)),
                shared.hex_to_int(job._version)
            )
            self.current_work = work
            bm1366.send_work(work)


    def start_job(self, job):
        self.stop_event.set()
        if self.job_thread:
            self.job_thread.join()

        self.stop_event.clear()
        self.job_thread = threading.Thread(target=self._receive)
        self.job_thread.start()

        self._start_with_random_extranonce2(job)


    def stop(self):
        self.stop_event.set()
        self.job_thread.join()
