import json
import os
import base64
from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto import Random


def encrypt(key, source, gen_hash=True, encode=True):
    if isinstance(source, str):
        source = bytes(source, 'latin-1')
    if gen_hash:
        key = key.encode('latin-1')
        key = SHA256.new(key).digest()
    else:
        key = bytes(key, 'latin-1')
    IV = Random.new().read(AES.block_size)
    encryptor = AES.new(key, AES.MODE_CBC, IV)
    padding = AES.block_size - len(source) % AES.block_size
    source += bytes([padding]) * padding
    data = IV + encryptor.encrypt(source)
    return base64.b64encode(data).decode("latin-1") if encode else data


def decrypt(key, source, gen_hash=True, decode=True):
    if isinstance(source, str):
        source = bytes(source, 'latin-1')
    if decode:
        source = base64.b64decode(source)
    if gen_hash:
        key = key.encode('latin-1')
        key = SHA256.new(key).digest()
    else:
        key = bytes(key, 'latin-1')
    IV = source[:AES.block_size]
    decrypter = AES.new(key, AES.MODE_CBC, IV)
    data = decrypter.decrypt(source[AES.block_size:])
    padding = data[-1]
    if data[-padding:] != bytes([padding]) * padding:
        raise ValueError("Invalid padding")
    return data[:-padding].decode('latin-1')


def encrypt_obj(obj, key, gen_hash=True):
    msg = json.dumps(obj)
    cipher = encrypt(key, msg, gen_hash)
    return cipher


def decrypt_obj(cipher, key, gen_hash=True):
    s = decrypt(key, cipher, gen_hash)
    return json.loads(s)


def get_random_key():
    session_key = os.urandom(32)
    return session_key.decode('latin-1')

