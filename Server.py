import rpyc
import random
import os
import json
from rpyc.utils.server import ThreadedServer
from rpyc.lib import setup_logger
from cryputils import encrypt
from cryputils import decrypt
from cryputils import decrypt_obj

ds_registry = {}
fs_registry = {}

KDC_IP = "127.0.0.1"
KDC_PORT = 8080
SERVER_KEY = "pwd5"
SERVER_ID = "m_server"

IP = "127.0.0.1"
PORT = 7487


class MasterServer(rpyc.Service):
    class ExposedServer:
        @staticmethod
        def register_node(node_id, type_node="ds"):
            if not node_id.startswith(type_node):
                print("Unable to verify identity for", node_id)
                return -1
            nonce = random.randint(0, 100000000)
            obj = {"server": SERVER_ID, "client": node_id, "nonce": nonce}
            dcon = rpyc.connect(KDC_IP, KDC_PORT)
            serv = dcon.root.ExposedKDC()
            token = serv.get_session_key(obj)
            if token == -1:
                print("Unable to get session key")
                return -1
            decrypted_obj = decrypt_obj(token, SERVER_KEY)
            chk_node_id = decrypted_obj["id"]
            chk_nonce = int(decrypted_obj["nonce"])
            if chk_nonce != nonce or node_id != chk_node_id:
                print("Registration failed for", node_id)
                return -1
            if type_node == "ds":
                ds_registry[node_id] = decrypted_obj["session_key"]
            elif type_node == "fs":
                fs_registry[node_id] = decrypted_obj["session_key"]
            return decrypted_obj["sub_token"]

        @staticmethod
        def nonce_handshake(node_id, enc_nonce, type_node="ds"):
            if type_node == "ds":
                if node_id not in ds_registry:
                    print("Nonce Handshake Failed for", node_id)
                    return -1
                session_key = ds_registry[node_id]
            elif type_node == "fs":
                if node_id not in fs_registry:
                    print("Nonce Handshake Failed for", node_id)
                    return -1
                session_key = fs_registry[node_id]
            dec_nonce = decrypt(session_key, enc_nonce, False)
            dec_nonce = int(dec_nonce) - 1
            snd_nonce = encrypt(session_key, str(dec_nonce), False)
            print(ds_registry)
            print(fs_registry)
            return snd_nonce


if __name__ == "__main__":
    t = ThreadedServer(MasterServer, hostname=IP, port=PORT, protocol_config={'allow_public_attrs': True})
    setup_logger(quiet=False, logfile=None)
    t.start()
