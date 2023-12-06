import RPi.GPIO as GPIO
import serial
import time
import logging
import random
import copy
import smbus
import os
import math

from rpi_hardware_pwm import HardwarePWM

import threading
from shared import shared

from . import bm1366
from . import influx


LM75_ADDRESS = 0x48
INFLUX_ENABLED = True
DEBUG_BM1366 = False

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


class Board:
    def set_fan_speed(self, speed):
        raise NotImplementedError

    def read_temperature(self):
        raise NotImplementedError

    def set_led(self, state):
        raise NotImplementedError

    def reset_func(self, state):
        raise NotImplementedError

    def shutdown(self):
        raise NotImplementedError

    def serial_port(self):
        raise NotImplementedError


class RPiHardware(Board):
    SDN_PIN = 11  # SDN, output, initial high
    PGOOD_PIN = 13  # PGOOD, input, floating
    NRST_PIN = 15  # NRST, output, initial high
    PWM_PIN = 12  # PWM output on Pin 12
    LED_PIN = 19  # LED 😍

    def __init__(self):
        # Setup GPIO
        GPIO.setmode(GPIO.BOARD)  # Use Physical pin numbering

        # Initialize GPIO Pins
        GPIO.setup(RPiHardware.SDN_PIN, GPIO.OUT, initial=GPIO.LOW)
        # Default is floating
        GPIO.setup(RPiHardware.PGOOD_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(RPiHardware.NRST_PIN, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setup(RPiHardware.LED_PIN, GPIO.OUT, initial=GPIO.LOW)

        # Create an SMBus instance
        self._bus = smbus.SMBus(1)  # 1 indicates /dev/i2c-1

        pwm = HardwarePWM(pwm_channel=0, hz=1000)
        pwm.start(80)  # full duty cycle

        # Initialize serial communication
        self._serial_port = serial.Serial(
            port="/dev/ttyS0",  # For GPIO serial communication use /dev/ttyS0
            baudrate=115200,    # Set baud rate to 115200
            bytesize=serial.EIGHTBITS,     # Number of data bits
            parity=serial.PARITY_NONE,     # No parity
            stopbits=serial.STOPBITS_ONE,  # Number of stop bits
            timeout=1                      # Set a read timeout
        )

        GPIO.output(RPiHardware.SDN_PIN, True)

        while (not self._is_power_good()):
            print("power not good ... waiting ...")
            time.sleep(5)

    def _is_power_good(self):
        return GPIO.input(RPiHardware.PGOOD_PIN)

    def set_fan_speed(self, speed):
        pass

    def read_temperature(self):
        data = self._bus.read_i2c_block_data(LM75_ADDRESS, 0, 2)

        # Convert the data to 12-bits
        return (data[0] << 4) | (data[1] >> 4)

    def set_led(self, state):
        GPIO.output(RPiHardware.LED_PIN, True if state else False)

    def reset_func(self, state):
        GPIO.output(RPiHardware.NRST_PIN, True if state else False)

    def shutdown(self):
        # disable buck converter
        logging.info("shutdown miner ...")
        GPIO.output(RPiHardware.SDN_PIN, False)
        self.set_led(False)

    def serial_port(self):
        return self._serial_port


class BM1366Miner:
    def __init__(self, network):
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
        self.led_thread = None
        self.led_event = threading.Event()
        self.network = network

        self.last_job_time = time.time()

        self.shares = list()

        if INFLUX_ENABLED:
            stats_name = "mainnet_stats" if network == shared.BitcoinNetwork.MAINNET else \
                "testnet_stats" if network == shared.BitcoinNetwork.TESTNET else "regtest_stats"
            self.influx = influx.Influx(stats_name)

    def shutdown(self):
        # signal the threads to end
        self.stop_event.set()

        # join all threads
        for t in [self.job_thread, self.receive_thread, self.temp_thread, self.led_thread, self.uptime_counter_thread]:
            t.join(5)

        self.hardware.shutdown()

    def get_name(self):
        return "PiAxe"

    def get_user_agent(self):
        return f"{self.get_name()}/0.1"

    def init(self):
        self.hardware = RPiHardware()
        self.serial_port = self.hardware.serial_port()

        # set the hardware dependent functions for serial and reset
        bm1366.ll_init(self._serial_tx_func, self._serial_rx_func,
                       self.hardware.reset_func)

        # init bm1366
        bm1366.init(485)
        logging.info("waiting for chipid response ...")
        init_response = bm1366.receive_work()

        if init_response.nonce != 0x00006613:
            raise Exception("bm1366 not detected")

        if INFLUX_ENABLED:
            self.influx.connect()
            try:
                self.influx.load_last_values()
            except Exception as e:
                logging.error("we really don't want to start without previous values: %s", e)
                self.hardware.shutdown()
                os._exit(0)

        self.set_difficulty(512)

        self.temp_thread = threading.Thread(target=self._monitor_temperature)
        self.temp_thread.start()

        self.receive_thread = threading.Thread(target=self._receive_thread)
        self.receive_thread.start()

        self.job_thread = threading.Thread(target=self._job_thread)
        self.job_thread.start()

        self.uptime_counter_thread = threading.Thread(target=self._uptime_counter_thread)
        self.uptime_counter_thread.start()

        self.led_thread = threading.Thread(target=self._led_thread)
        self.led_thread.start()

    def _uptime_counter_thread(self):
        logging.info("uptime counter thread started ...")
        while not self.stop_event.is_set():
            with self.influx.stats.lock:
                self.influx.stats.total_uptime += 1
                self.influx.stats.uptime += 1
            time.sleep(1)

        logging.info("uptime counter thread ended ...")

    def _led_thread(self):
        logging.info("LED thread started ...")
        led_state = True
        while not self.stop_event.is_set():
            # if for more than 5 minutes no new job is received
            # we flash the light faster
            if time.time() - self.last_job_time > 5*60:
                led_state = not led_state
                self.hardware.set_led(led_state)
                time.sleep(0.25)
                continue

            # this gets triggered in 2s intervals
            # .wait() doesn't work reliably because it happens
            # that the submit method hangs forever and the
            # event wouldn't be fired then
            if self.led_event.is_set():
                self.led_event.clear()
                led_state = not led_state
                self.hardware.set_led(led_state)
                continue

            time.sleep(0.25)

        logging.info("LED thread ended ...")

    def _monitor_temperature(self):
        while not self.stop_event.is_set():
            temp = self.hardware.read_temperature()
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
                self.hardware.shutdown()
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
            if DEBUG_BM1366:
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
        # restrict to min 512
        difficulty = max(difficulty, 512)

        self._difficulty = difficulty
        self._set_target(shared.calculate_target(difficulty))
        bm1366.set_job_difficulty_mask(difficulty)

        if INFLUX_ENABLED:
            with self.influx.stats.lock:
                self.influx.stats.difficulty = difficulty

    def set_submit_callback(self, cb):
        self.submit_cb = cb



    def accepted_callback(self):
        with self.influx.stats.lock:
            self.influx.stats.accepted += 1

    def not_accepted_callback(self):
        with self.influx.stats.lock:
            self.influx.stats.not_accepted += 1

    def _receive_thread(self):
        logging.info('receiving thread started ...')
        #last_response = time.time()
        while not self.stop_event.is_set():
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

                if DEBUG_BM1366:
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

                    if result_job_id not in self._jobs:
                        logging.debug("internal jobid %d not found", result_job_id)
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

                    is_valid, hash, zeros = shared.verify_work(difficulty, job, result)

                    if INFLUX_ENABLED:
                        with self.influx.stats.lock:
                            network_target, network_zeros = shared.nbits_to_target(job._nbits)
                            logging.debug("network-target: %s (%d)", network_target, network_zeros)
                            logging.debug("found hash:     %s (%d)", hash, zeros)

                            if hash < network_target:
                                logging.info("it seems we found a block!")
                                self.influx.stats.blocks_found += 1
                                self.influx.stats.total_blocks_found += 1

                            self.influx.stats.invalid_shares += 1 if not is_valid else 0
                            self.influx.stats.valid_shares += 1 if is_valid else 0
                            self.shares.append((1, self.influx.stats.difficulty, time.time()))
                            self.influx.stats.hashing_speed = self.hash_rate()
                            hash_difficulty = shared.calculate_difficulty_from_hash(hash)
                            self.influx.stats.best_difficulty = max(self.influx.stats.best_difficulty, hash_difficulty)
                            self.influx.stats.total_best_difficulty = max(self.influx.stats.total_best_difficulty, hash_difficulty)

                    # restart miner with new extranonce2
                    self.new_job_event.set()

                # submit result without lock on the job!
                if not is_valid:
                    # if its invalid it would be rejected
                    # we don't try it but we can count it to not_accepted
                    self.not_accepted_callback()
                    logging.error("invalid result!")
                    continue


                logging.info("valid result")
                if not self.submit_cb:
                    logging.error("no submit callback set")
                elif not self.submit_cb(result):
                    self.influx.stats.pool_errors += 1

        logging.info('receiving thread ended ...')



    def _job_thread(self):
        logging.info("job thread started ...")
        current_time = time.time()
        while not self.stop_event.is_set():
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
                self._latest_work_id = ((self._internal_id << 3) & 0x7f) + 0x08

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

                self.led_event.set()

                bm1366.send_work(work)

        logging.info("job thread ended ...")

    def clean_jobs(self):
        with self.job_lock:
            logging.info("cleaning jobs ...")
            self._jobs = dict()
            self.current_job = None

    def start_job(self, job):
        logging.info("starting new job %s", job._job_id)
        self.last_job_time = time.time()
        with self.job_lock:
            self.current_job = job
            self.new_job_event.set()

