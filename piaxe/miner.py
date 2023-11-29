import RPi.GPIO as GPIO
import serial
import time
import logging
import random
import copy
import smbus
import os

from rpi_hardware_pwm import HardwarePWM

import threading
from shared import shared

from . import bm1366
from . import influx

SDN_PIN = 11  # SDN, output, initial high
PGOOD_PIN = 13  # PGOOD, input, floating
NRST_PIN = 15  # NRST, output, initial high
PWM_PIN = 12  # PWM output on Pin 12
LED_PIN = 19 # LED 😍

LM75_ADDRESS = 0x48
INFLUX_ENABLED = True

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

        self._internal_id = 0
        self._latest_work_id = 0
        self._jobs = dict()
        self._timestamp_last_chipid = 0

        self.tracker_send = list()
        self.tracker_received = list()

        self.job_thread = None
        self.receive_thread = None
        self.temp_thread = None
        self.job_lock = threading.Lock()
        self.serial_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.new_job_event = threading.Event()

        self.shares = list()

        if INFLUX_ENABLED:
            self.influx = influx.Influx()


    def get_name(self):
        return "PiAxe"

    def init(self):
        # Setup GPIO
        GPIO.setmode(GPIO.BOARD)  # Use Physical pin numbering

        # Initialize GPIO Pins
        GPIO.setup(SDN_PIN, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(PGOOD_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Default is floating
        GPIO.setup(NRST_PIN, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setup(LED_PIN, GPIO.OUT, initial=GPIO.LOW)

        # Create an SMBus instance
        self._bus = smbus.SMBus(1)  # 1 indicates /dev/i2c-1

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

        if INFLUX_ENABLED:
            self.influx.connect()

        self.set_difficulty(512)

        self.temp_thread = threading.Thread(target=self._read_temperature)
        self.temp_thread.start()

        self.receive_thread = threading.Thread(target=self._receive_thread)
        self.receive_thread.start()

        self.job_thread = threading.Thread(target=self._job_thread)
        self.job_thread.start()



    def set_led(self, state):
        GPIO.output(LED_PIN, True if state else False)

    def shutdown(self):
        # disable buck converter
        logging.info("shutdown miner ...")
        GPIO.output(SDN_PIN, False)
        self.set_led(False)

    def _read_temperature(self):
        while True:
            # Read two bytes of data from the temperature register
            data = self._bus.read_i2c_block_data(LM75_ADDRESS, 0, 2)

            # Convert the data to 12-bits
            temp = (data[0] << 4) | (data[1] >> 4)

            # Convert to a signed 12-bit value
            if temp > 2047:
                temp -= 4096

            # Convert to Celsius
            celsius = temp * 0.0625
            logging.info("temperature: %.3f", celsius)

            if INFLUX_ENABLED:
                with self.influx.stats.lock:
                    self.influx.stats.temp = celsius

            if celsius > 70.0:
                logging.error("too hot, shutting down ...")
                self.shutdown()
                os._exit(1)

            time.sleep(1.5)

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


    def hash_rate(self, time_period=600):
        current_time = time.time()
        total_work = 0

        for shares, difficulty, timestamp in self.shares:
            # Consider shares only in the last 10 minutes
            if current_time - timestamp <= time_period:
                total_work += shares * (difficulty << 32)

        # Hash rate in H/s (Hashes per second)
        hash_rate_hps = total_work / time_period

        # Convert hash rate to GH/s
        hash_rate_ghps = hash_rate_hps / 1e9
        return hash_rate_ghps

    def _set_target(self, target):
        self._target = '%064x' % target

    def set_difficulty(self, difficulty):
        self._difficulty = difficulty
        self._set_target(shared.calculate_target(difficulty))
        bm1366.set_job_difficulty_mask(difficulty)

        if INFLUX_ENABLED:
            with self.influx.stats.lock:
                self.influx.stats.difficulty = difficulty

    def set_submit_callback(self, cb):
        self.submit_cb = cb

    def _receive_thread(self):
        logging.info('receiving thread started ...')
        #last_response = time.time()
        while True:
            if self.stop_event.is_set():
                return

            byte = self._serial_rx_func(11, 100, debug=False)

            if not byte:
                continue

            for i in range(0, len(byte)):
                self._buffer[self._write_index % 64] = byte[i]
                self._write_index += 1

            if self._write_index - self._read_index >= 11 and self._buffer[self._read_index % 64] == 0xaa and self._buffer[(self._read_index + 1) % 64] == 0x55:
                data = bytearray([0] * 11)
                for i in range(0, 11):
                    data[i] = self._buffer[self._read_index % 64]
                    self._read_index += 1

                logging.debug("<- %s", bytes(data).hex())

                asic_result = bm1366.AsicResult().from_bytes(bytes(data))
                if not asic_result or not asic_result.nonce:
                    continue

                if asic_result.nonce == 0x6613:
                    self._timestamp_last_chipid = time.time()
                    continue

                with self.job_lock:
                    last_response = time.time()
                    result_job_id = asic_result.job_id & 0xf8
                    logging.debug("work received %02x", result_job_id)

                    #if result_job_id != self._latest_work_id:
                    #    logging.warn("discarding result ... too old")
                    if result_job_id not in self._jobs:
                        logging.error("internal jobid %d not found", result_job_id)
                        continue

                    saved_job = self._jobs[result_job_id]
                    job = saved_job['job']
                    work = saved_job['work']
                    difficulty = saved_job['difficulty']

                    if result_job_id != work.id:
                        logging.error("mismatch ids")
                        continue

                    result = dict(
                        job_id = job._job_id,
                        extranonce2 = job._extranonce2, #shared.int_to_hex32(job._extranonce2),
                        ntime = job._ntime,
                        nonce = shared.int_to_hex32(asic_result.nonce),
                        version = shared.int_to_hex32(bm1366.reverse_uint16(asic_result.version) << 13),
                    )
                    is_valid, hash = shared.verify_work(difficulty, job, result)

                    if not is_valid:
                        logging.error("invalid result!")
                    else:
                        self.submit_cb(result)

                    if INFLUX_ENABLED:
                        with self.influx.stats.lock:
                            self.influx.stats.invalid_shares += 1 if not is_valid else 0
                            self.influx.stats.valid_shares += 1 if is_valid else 0
                            self.shares.append((1, self.influx.stats.difficulty, time.time()))
                            self.influx.stats.hashing_speed = self.hash_rate()
                            hash_difficulty = shared.calculate_difficulty_from_hash(hash)
                            self.influx.stats.best_difficulty = max(self.influx.stats.best_difficulty, hash_difficulty)

                    # restart miner with new extranonce2
                    self.new_job_event.set()




    def _job_thread(self):
        logging.info("job thread started ...")
        current_time = time.time()
        led_state = True
        while True:
            self.new_job_event.wait(1.5)
            self.new_job_event.clear()

            with self.job_lock:
                if not self.current_job:
                    logging.info("no job ...")
                    time.sleep(1)
                    continue


                extranonce2 = random.randint(0, 2**31-1)
                logging.debug("new extranonce2 %08x", extranonce2)
                self.current_job.set_extranonce2(extranonce2)

                self._internal_id += 1
                self._latest_work_id = ((self._internal_id << 3) & 0x7f) + 0x10

                work = bm1366.WorkRequest()
                logging.debug("new work %02x", self._latest_work_id)
                work.create_work(
                    self._latest_work_id,
                    0x00000000,
                    shared.hex_to_int(self.current_job._nbits),
                    shared.hex_to_int(self.current_job._ntime),
                    shared.reverse_bytes(shared.hex_to_bytes(self.current_job._merkle_root)),
                    shared.reverse_bytes(shared.hex_to_bytes(self.current_job._prevhash)),
                    shared.hex_to_int(self.current_job._version)
                )
                self.current_work = work

                # make deepcopies
                self._jobs[self._latest_work_id] = {
                    'job': copy.deepcopy(self.current_job),
                    'work': copy.deepcopy(self.current_work),
                    'difficulty': self._difficulty
                }

                # do it every now and then ...
                bm1366.request_chip_id()

                # logging.info("health-checking ...")
                # while True:
                #     bm1366.request_chip_id()
                #     time.sleep(1)
                #     if time.time() - self._timestamp_last_chipid < 2000:
                #         break
                #     logging.info("health-checking retry ...")

                # logging.info("health-checking success")

                bm1366.send_work(work)

                led_state = not led_state
                self.set_led(led_state)

                # remember when we started the work
                current_time = time.time()






    def start_job(self, job):
        logging.info("starting new job %s", job._job_id)
        with self.job_lock:
            self.current_job = job
            self.new_job_event.set()


    def stop(self):
        self.stop_event.set()
        self.job_thread.join()
