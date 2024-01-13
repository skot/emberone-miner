import struct
import hashlib
import logging
import random
import binascii
import json
from enum import Enum
import bech32


def swap_endian_word(hex_word):
  '''Swaps the endianness of a hexidecimal string of a word and converts to a binary string.'''

  message = binascii.unhexlify(hex_word)
  if len(message) != 4: raise ValueError('Must be 4-byte word')
  return message[::-1]

def swap_endian_words(hex_words):
    '''Swaps the endianness of a hexadecimal string of words and keeps as binary data.'''
    message = binascii.unhexlify(hex_words)
    if len(message) % 4 != 0:
        raise ValueError('Must be 4-byte word aligned')
    return b''.join([message[4 * i: 4 * i + 4][::-1] for i in range(len(message) // 4)])


def sha256d(message):
  '''Double SHA256 Hashing function.'''

  return hashlib.sha256(hashlib.sha256(message).digest()).digest()

def count_leading_zeros(hex_string):
    # Convert the hexadecimal string to a binary string
    binary_string = bin(int(hex_string, 16))[2:].zfill(len(hex_string) * 4)

    # Count the leading zeros
    count = 0
    for char in binary_string:
        if char == '0':
            count += 1
        else:
            break

    return count

def swap_endianness_32bit(byte_array):
    # Ensure the byte array length is a multiple of 4 (32 bits)
    if len(byte_array) % 4 != 0:
        raise ValueError("Byte array length must be a multiple of 4.")

    swapped_array = bytearray()

    # Process each 32-bit chunk
    for i in range(0, len(byte_array), 4):
        # Unpack the 32-bit word in little-endian format
        word, = struct.unpack('<I', byte_array[i:i+4])

        # Pack the word back into big-endian format and append to the result
        swapped_array.extend(struct.pack('>I', word))

    return swapped_array

def reverse_bytes(data):
    data = bytearray(data)
    len_data = len(data)
    for i in range(len_data // 2):
        # Swap bytes
        temp = data[i]
        data[i] = data[len_data - 1 - i]
        data[len_data - 1 - i] = temp
    return bytes(data)

def hex_to_be(hex):
    bin_be = swap_endian_words(hex)
    bin_be = reverse_bytes(bin_be)
    return bin_be

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
        self._extranonce1 = extranonce1
        self._extranonce2_size = extranonce2_size

        # choose random extranonce
        extranonce2 = random.randint(0, 2**31-1)
        self.set_extranonce2(extranonce2)

    def _limit_extranonce2(self, extranonce2):
        # Convert extranonce2 to hex
        hex_extranonce2 = int_to_hex32(extranonce2)

        # Ensure the hex string length is twice extranonce2_size
        hex_extranonce2 = hex_extranonce2[:2 * self._extranonce2_size].zfill(2 * self._extranonce2_size)

        return hex_extranonce2

    def set_extranonce2(self, extranonce2):
        self._extranonce2 = self._limit_extranonce2(extranonce2)

        coinbase_bin = binascii.unhexlify(self._coinb1) + binascii.unhexlify(self._extranonce1) + binascii.unhexlify(self._extranonce2) + binascii.unhexlify(self._coinb2)
        coinbase_hash_bin = sha256d(coinbase_bin)

        # save coinbase_hex for verification
        self.coinbase_hex = binascii.hexlify(coinbase_bin).decode('utf-8')

        self._merkle_root_bin = coinbase_hash_bin
        for branch in self._merkle_branches:
            self._merkle_root_bin = sha256d(self._merkle_root_bin + binascii.unhexlify(branch))

        self._merkle_root = binascii.hexlify(swap_endian_words(binascii.hexlify(self._merkle_root_bin).decode('utf8'))).decode('utf8')



    def to_dict(self):
        # Convert object to a dictionary
        return {
            "job_id": self._job_id,
            "prevhash": self._prevhash,
            "coinb1": self._coinb1,
            "coinb2": self._coinb2,
            "merkle_branches": self._merkle_branches,
            "version": self._version,
            "nbits": self._nbits,
            "ntime": self._ntime,
            "extranonce1": self._extranonce1,
            "extranonce2_size": self._extranonce2_size,
            # You might need to convert binary data to a string format
            "extranonce2": self._extranonce2,
            "merkle_root": self._merkle_root
        }

    @classmethod
    def from_dict(cls, data):
        # Create a new instance from a dictionary
        return cls(
            data["job_id"],
            data["prevhash"],
            data["coinb1"],
            data["coinb2"],
            data["merkle_branches"],
            data["version"],
            data["nbits"],
            data["ntime"],
            data["extranonce1"],
            data["extranonce2_size"],
        )

    def to_json(self):
        # Serialize to JSON
        return json.dumps(self.to_dict(), indent=4)

    @classmethod
    def from_json(cls, json_str):
        # Deserialize from JSON
        data = json.loads(json_str)
        return cls.from_dict(data)

    def deserialize_coinbase(self):
        hex_string = self.coinbase_hex
        # Helper function to read variable integer (CompactSize)
        def read_varint(hex_data):
            size = int(hex_data[:2], 16)
            if size < 0xfd:
                return size, hex_data[2:]
            if size == 0xfd:
                return int(hex_data[2:6], 16), hex_data[6:]
            if size == 0xfe:
                return int(hex_data[2:10], 16), hex_data[10:]
            if size == 0xff:
                return int(hex_data[2:18], 16), hex_data[18:]

        def decode_script_number(buffer, max_length=4, minimal=True):
            length = len(buffer)
            if length == 0:
                return 0
            if length > max_length:
                raise TypeError('Script number overflow')
            if minimal:
                if (buffer[-1] & 0x7f) == 0:
                    if length <= 1 or (buffer[-2] & 0x80) == 0:
                        raise ValueError('Non-minimally encoded script number')

            # 32-bit / 24-bit / 16-bit / 8-bit
            result = 0
            for i in range(length):
                result |= buffer[i] << (8 * i)

            if buffer[-1] & 0x80:
                return -(result & ~(0x80 << (8 * (length - 1))))
            return result

        # Helper function to convert little endian hex to int
        def le_hex_to_int(hex_data):
            return int.from_bytes(bytes.fromhex(hex_data), 'little')

        # Cursor to keep track of position
        cursor = 0

        # Deserialize the transaction
        tx = {}

        # Version
        tx['version'] = le_hex_to_int(hex_string[cursor:cursor + 8])
        cursor += 8

        # Input Count
        input_count, hex_string = read_varint(hex_string[cursor:])
        cursor = 0  # reset cursor as hex_string is now shorter
        tx['input_count'] = input_count

        # Inputs
        tx['inputs'] = []
        for _ in range(input_count):
            input = {}

            # Previous Output Hash
            input['previous_output_hash'] = hex_string[cursor:cursor + 64]
            cursor += 64

            # Previous Output Index
            input['previous_output_index'] = hex_string[cursor:cursor + 8]
            cursor += 8

            # Coinbase Data Size
            coinbase_size, hex_string = read_varint(hex_string[cursor:])
            cursor = 0  # reset cursor as hex_string is now shorter
            input['coinbase_size'] = coinbase_size

            # Coinbase Data
            input['coinbase_data'] = hex_string[cursor:cursor + coinbase_size * 2]
            cursor += coinbase_size * 2

            # extract blocknumber
            if tx['version'] == 2:
                coinbase_data_bytes = binascii.unhexlify(input['coinbase_data'])
                height_num_bytes = coinbase_data_bytes[0]
                tx['height'] = decode_script_number(coinbase_data_bytes[1:1+height_num_bytes])
            else:
                tx['height'] = None

            # Sequence
            input['sequence'] = hex_string[cursor:cursor + 8]
            cursor += 8

            tx['inputs'].append(input)

        # Output Count
        output_count, hex_string = read_varint(hex_string[cursor:])
        cursor = 0  # reset cursor as hex_string is now shorter
        tx['output_count'] = output_count

        # Outputs
        tx['outputs'] = []
        for _ in range(output_count):
            output = {}

            # Value
            output['value'] = le_hex_to_int(hex_string[cursor:cursor + 16])
            cursor += 16

            # Script Length
            script_length, hex_string = read_varint(hex_string[cursor:])
            cursor = 0  # reset cursor as hex_string is now shorter
            output['script_length'] = script_length

            # Script
            output['script'] = hex_string[cursor:cursor + script_length * 2]
            cursor += script_length * 2

            tx['outputs'].append(output)

        # Locktime
        tx['locktime'] = le_hex_to_int(hex_string[cursor:cursor + 8])

        return tx


class BitcoinNetwork(Enum):
    MAINNET = 1
    TESTNET = 2
    REGTEST = 3
    UNKNOWN = 4

def detect_btc_network(address):
    if address.startswith("1") or address.startswith("3") or address.startswith("bc1"):
        return BitcoinNetwork.MAINNET
    elif address.startswith("m") or address.startswith("n") or address.startswith("2") or address.startswith("tb1"):
        return BitcoinNetwork.TESTNET
    elif address.startswith("bcrt1"):
        return BitcoinNetwork.REGTEST
    else:
        return BitcoinNetwork.UNKNOWN

def int_to_hex32(v):
    return f"{v:08x}"

def int_to_hex256(v):
    return f"{v:064x}"

def int_to_hex16(v):
    return f"{v:04x}"

def int_to_bytes32(i):
    return struct.pack('<I', i)

def hex_to_int(v):
    return int(v, 16)

def bytes_to_hex(i):
    return binascii.hexlify(i).decode('utf8')

def hex_to_bytes(i):
    return binascii.unhexlify(i)

def int_to_bin32(v, sep=0):
    bin = ""
    for bit in range(31, -1, -1):
        bin += "1" if v & (1<<bit) else "0"
        if sep and bit % sep == 0:
            bin += " "

    return bin


def calculate_target(difficulty):
    if difficulty < 0:
        raise Exception('Difficulty must be non-negative')

    # Compute target
    if difficulty == 0:
        target = 2 ** 256 - 1
    else:
        target = min(int((0xffff0000 * 2 ** (256 - 64) + 1) / difficulty - 1 + 0.5), 2 ** 256 - 1)

    return target

def calculate_difficulty_from_hash(hash_hex):
    # Convert hash from hex to integer
    hash_int = int(hash_hex, 16)

    # Difficulty 1 Target
    diff1_target = 0xffff0000 * 2 ** (256 - 64)

    # Calculate difficulty
    difficulty = diff1_target / hash_int

    return difficulty

def nbits_to_target(nbits):
    nbits = int(nbits, 16)

    # Split nbits into the exponent and coefficient
    exponent = nbits >> 24
    coefficient = nbits & 0xffffff

    # Convert to 256-bit target
    target = coefficient << (8 * (exponent - 3))

    # Format target as a 64-character hexadecimal string
    target_hex = format(target, '064x')

    leading_zeros = count_leading_zeros(target_hex)

    return target_hex, leading_zeros

def verify_work(difficulty, job, result):
#    print(job.to_json())
#    print(json.dumps(result, indent=4))

    if job._job_id != result['job_id']:
        raise Exception("job_ids mismatch")

    header = swap_endian_word(int_to_hex32(int(job._version, 16) ^ int(result['version'], 16)))
    header += swap_endian_words(job._prevhash)
    header += swap_endian_words(job._merkle_root)
    header += swap_endian_words(result['ntime'])
    header += swap_endian_words(job._nbits)
    header += swap_endian_words(result['nonce'])
    logging.debug("header: %s", bytearray(header).hex())

    target = int_to_hex256(calculate_target(difficulty))

    # Hash the header twice using SHA-256.
    hash_buffer = hashlib.sha256(header).digest()
    hash_result = hashlib.sha256(hash_buffer).digest()
    hash_str = bytearray(hash_result).hex()
    hash_be = swap_endianness_32bit(hex_to_be(hash_str))
    hash_str = bytearray(hash_be).hex()
    leading_zeros = count_leading_zeros(hash_str)

    return hash_str < target, hash_str, leading_zeros

def get_network_target(difficulty):
    target = int_to_hex256(calculate_target(difficulty))
    leading_zeros = count_leading_zeros(target)
    return target, leading_zeros


def decode_bech32(address):
    hrp = address.split('1')[0]

    # Decoding the Bech32 address to get the witness version and witness program
    hrp, decoded_data = bech32.decode(hrp, address)
    if decoded_data is None:
        raise ValueError("Invalid Bech32 address")

    return bytes(decoded_data)

def get_scriptpubkey_from_bech32(address):
    # Decoding the Bech32 address
    decoded_data = decode_bech32(address)
    # The first byte is the witness version
    witness_version = decoded_data[0]
    # The rest is the witness program (hash)
    witness_program = decoded_data[1:]
    # Constructing the scriptPubKey
    return witness_version, witness_program

def verify_solo(btc_address, coinb):
    if coinb['output_count'] < 1:
        raise Exception("no outputs found")

    witness_version, witness_program = get_scriptpubkey_from_bech32(btc_address)
    scriptpubkey = binascii.hexlify(witness_program).decode('utf-8')

    value_total = 0
    value_our = 0
    for i, output in enumerate(coinb['outputs']):
        if i == 0:
            #print(output['script'])
            if scriptpubkey not in output['script']:
                raise Exception("script pubkey of our address not found")
            value_our += output['value']

        value_total += output['value']

    if value_our != value_total:
        raise Exception("not getting all rewards! %d vs %d", value_our, value_total)

    return True, value_our, value_total



if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    difficulty = 0.0032
    job_dict = {
        "job_id": "10",
        "prevhash": "b82cc386d81b16238daa4906ae4fc0599d9d145347bacdac0000007b00000000",
        "coinb1": "02000000010000000000000000000000000000000000000000000000000000000000000000ffffffff1903cac3265c7075626c69632d706f6f6c5c",
        "coinb2": "ffffffff02bdcd1200000000001976a914fbff95b4e35aca918d26e157392ea1643a2dc28388ac0000000000000000266a24aa21a9edac9132f342173ab4e3cfe34f393b1ce7d46226c100426d02667fc7d89dc7942f00000000",
        "merkle_branches": [
            "2c4b311ff57d11518cab724b93286f33dd441391e2b63d2a19c901200390ce91",
            "1265661d1c0e2839b78e2d65eaadf04941b7fffd27722f4059bdd3c617dca326",
            "7956bf0ecaf8a0a797e1a9517a535f9b1f076ca0e4b5db460a0bef4c0c105125",
            "ea2569f34f3189ca7f4c6f4c1b856551e8a94bae47ee6fdeb6eae2c144fd333a"
        ],
        "version": "20000000",
        "nbits": "1924f3f1",
        "ntime": "6562e8e6",
        "extranonce1": "44f454dd",
        "extranonce2_size": 4,
        "extranonce2": "0x6eaaf700",
        "merkle_root": "f7614f139a8c70b1ed6bc55e29a242418f22ba99d2efdf901366fc4c4c5a358c"
    }
    result = {
        "job_id": "10",
        "extranonce2": "0x6eaaf700",
        "ntime": "6562e8e6",
        "nonce": "018ced64",
        "version": "6072000"
    }
    job = Job.from_dict(job_dict)

    print(verify_work(job, result))
