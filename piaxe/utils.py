import sys
import hashlib
import struct
import binascii

def swab32(v):
    return ((v << 24) & 0xFF000000) | \
           ((v << 8) & 0x00FF0000) | \
           ((v >> 8) & 0x0000FF00) | \
           ((v >> 24) & 0x000000FF)

def flip32bytes(src):
    # Ensure the input is a bytearray for mutability.
    if not isinstance(src, bytearray):
        raise TypeError("src must be a bytearray")
    # Ensure the input length is a multiple of 4.
    if len(src) % 4 != 0:
        raise ValueError("src length must be a multiple of 4")

    dest = bytearray(len(src))
    for i in range(0, len(src), 4):
        # Interpret the next 4 bytes of `src` as a 32-bit integer in native endianness
        word, = struct.unpack('<I', src[i:i+4])
        # Swap the byte order of the 32-bit word
        swapped_word = swab32(word)
        # Pack the swapped word back into the byte array in native endianness
        dest[i:i+4] = struct.pack('<I', swapped_word)
    return dest

def swap_endian_words(hex_words):
    if len(hex_words) % 8 != 0:
        sys.stderr.write("Must be 4-byte word aligned\n")
        sys.exit(1)

    binary_length = len(hex_words) // 2
    output = bytearray(binary_length)

    for i in range(0, binary_length, 4):
        for j in range(4):
            byte_val = int(hex_words[(i + j) * 2:(i + j) * 2 + 2], 16)

            output[i + (3 - j)] = byte_val

    return output

def reverse_bytes(data):
    len_data = len(data)
    for i in range(len_data // 2):
        # Swap bytes
        temp = data[i]
        data[i] = data[len_data - 1 - i]
        data[len_data - 1 - i] = temp
    return data

def hex2val(hex_char):
    if '0' <= hex_char <= '9':
        return ord(hex_char) - ord('0')
    if 'A' <= hex_char.upper() <= 'F':
        return ord(hex_char.upper()) - ord('A') + 10
    raise ValueError(f"Invalid hex character: {hex_char}")

def hex2bin(hex_str):
    return bytearray.fromhex(hex_str)

def hex_to_be(hex):
    bin_be = swap_endian_words(hex)
    bin_be = reverse_bytes(bin_be)
    return bin_be

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