import threading
import struct
import binascii
from utils import utils
import time

class Job:
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
        target,
        extranonce1,
        extranonce2_size,
        max_nonce=0x7fffffff,
    ):
        # Job parts from the mining.notify command
        self._job_id = job_id
        self._prevhash = prevhash
        self._coinb1 = coinb1
        self._coinb2 = coinb2
        self._merkle_branches = [ b for b in merkle_branches ]
        self._version = version
        self._nbits = nbits
        self._ntime = ntime

        self._max_nonce = max_nonce

        # Job information needed to mine from mining.subsribe
        self._target = target
        self._extranonce1 = extranonce1
        self._extranonce2_size = extranonce2_size

        # Flag to stop this job's mine coroutine
        self._done = False

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
        if difficulty < 0: raise self.StateException('Difficulty must be non-negative')

        # Compute target
        if difficulty == 0:
            target = 2 ** 256 - 1
        else:
            target = min(int((0xffff0000 * 2 ** (256 - 64) + 1) / difficulty - 1 + 0.5), 2 ** 256 - 1)

        self._difficulty = difficulty
        self._set_target(target)

    def set_submit_callback(self, cb):
        self.submit_cb = cb


    def _merkle_root_bin(self, extranonce2_bin):
        '''Builds a merkle root from the merkle tree'''
        job = self.current_job
        coinbase_bin = binascii.unhexlify(job._coinb1) + binascii.unhexlify(job._extranonce1) + extranonce2_bin + binascii.unhexlify(job._coinb2)
        coinbase_hash_bin = utils.sha256d(coinbase_bin)

        merkle_root = coinbase_hash_bin
        for branch in job._merkle_branches:
            merkle_root = utils.sha256d(merkle_root + binascii.unhexlify(branch))
        return merkle_root

    def _mine(self):
        t0 = time.time()

        job = self.current_job

        # choose random extranonce
        extranonce2 = 0 #random.randint(0, 2**31-1) # 0 to 7fffffff
        extranonce2_bin = struct.pack('<I', extranonce2)
        merkle_root_bin = self._merkle_root_bin(extranonce2_bin)

        for rolled_version in range(12345, 2**16):
            version_hex = hex(int(job._version, 16) | (rolled_version << 13))[2:]

            header_prefix_bin = utils.swap_endian_word(version_hex) + utils.swap_endian_words(job._prevhash) + merkle_root_bin + utils.swap_endian_word(job._ntime) + utils.swap_endian_word(job._nbits)
            for nonce in range(0, job._max_nonce):
                # This job has been asked to stop
                if self.stop_event.is_set():
                    job._dt += (time.time() - t0)
                    return

                # Proof-of-work attempt
                nonce_bin = struct.pack('<I', nonce)
                pow = binascii.hexlify(utils.sha256d(header_prefix_bin + nonce_bin)[::-1]).decode("utf8")

                # Did we reach or exceed our target?
                result = None
                if pow <= self._target: # or pow < job._target:
                    result = dict(
                        job_id = job._job_id,
                        extranonce2 = binascii.hexlify(extranonce2_bin).decode("utf8"),
                        ntime = str(job._ntime),                    # Convert to str from json unicode
                        nonce = binascii.hexlify(nonce_bin[::-1]).decode("utf8"),
                        version = hex(rolled_version << 13)[2:],
                    )
                    job._dt += (time.time() - t0)
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


