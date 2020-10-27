import rpyc
import os
import json
from rpyc.utils.server import ThreadedServer
from rpyc.lib import setup_logger
from cryputils import *

key_dict = {}

class KDCServer(rpyc.Service):
    class exposed_KDC:
        @staticmethod
        def get_session_key(obj):
            alice = obj["server"]
            bob = obj["client"]
            nonce = obj["nonce"]
            if key_dict.get(alice) is None:
                return -1
            if key_dict.get(bob) is None:
                return -1
            alice_secret = key_dict[alice]
            bob_secret = key_dict[bob]
            session_key = get_random_key()
            enc_bob = {"id": alice, "session_key": session_key}
            enc_bob = encrypt_obj(enc_bob, bob_secret)
            token = {"nonce": nonce, "id": bob, "session_key": session_key, "sub_token": enc_bob}
            token = encrypt_obj(token, alice_secret)
            return token


if __name__ == "__main__":
    host = "127.0.0.1"
    port = 8080
    with open('db.json', 'r') as f:
        json_dat = f.read()
        key_dict = json.loads(json_dat)
    t = ThreadedServer(KDCServer, hostname=host, port=port, protocol_config={'allow_public_attrs': True})
    setup_logger(quiet=False, logfile=None)
    t.start()