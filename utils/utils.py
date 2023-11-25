import binascii
import hashlib

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