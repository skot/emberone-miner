import threading
import struct
import binascii
from shared import shared
import time
import logging

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

        # Hash metrics (start time, delta time, total hashes)
        self._dt = 0.0
        self._hash_count = 0

class CPUMiner:
    def __init__(self):
        self.current_job = None
        self.job_thread = None
        self.job_lock = threading.Lock()
        self.stop_event = threading.Event()

        self.set_difficulty(64)

    def init(self):
        pass

    def hashrate(self):
        '''The current hashrate, or if stopped hashrate for the job's lifetime.'''
        if self._dt == 0:
            return 0.0
        return self._hash_count / self._dt

    def _set_target(self, target):
        self._target = '%064x' % target

    def set_difficulty(self, difficulty):
        self._difficulty = difficulty
        self._set_target(shared.calculate_target(difficulty))

    def set_submit_callback(self, cb):
        self.submit_cb = cb


    def _mine(self):
        t0 = time.time()

        job = self.current_job

        for rolled_version in range(12345, 2**16):
            version_hex = shared.int_to_hex32(int(job._version, 16) | (rolled_version << 13))

            header_prefix_bin = shared.swap_endian_word(version_hex)
            header_prefix_bin += shared.swap_endian_words(job._prevhash)
            header_prefix_bin += shared.swap_endian_words(job._merkle_root)
            header_prefix_bin += shared.swap_endian_word(job._ntime)
            header_prefix_bin += shared.swap_endian_word(job._nbits)
            for nonce in range(0, job._max_nonce):
                # This job has been asked to stop
                if self.stop_event.is_set():
                    job._dt += (time.time() - t0)
                    return

                # Proof-of-work attempt
                nonce_bin = shared.int_to_bytes32(nonce)
                pow = shared.bytes_to_hex(shared.sha256d(header_prefix_bin + nonce_bin)[::-1])
                # Did we reach or exceed our target?
                result = None
                if pow <= self._target: # or pow < job._target:
                    result = dict(
                        job_id = job._job_id,
                        extranonce2 = job._extranonce2,
                        ntime = str(job._ntime),                    # Convert to str from json unicode
                        nonce = shared.bytes_to_hex(nonce_bin[::-1]),
                        version = shared.int_to_hex32(rolled_version << 13),
                    )
                    job._dt += (time.time() - t0)
                    if not shared.verify_work(self._difficulty, job, result):
                        logging.error("invalid result!")
                    self.submit_cb(result)

                t0 = time.time()
                job._hash_count += 1

    def start_job(self, job):
        self.stop_event.set()
        if self.job_thread:
            self.job_thread.join()

        self.stop_event.clear()
        self.current_job = job
        self.job_thread = threading.Thread(target=self._mine)
        self.job_thread.start()

    def stop(self):
        self.stop_event.set()
        self.job_thread.join()


