import rpyc
import random
import os
import json
from rpyc.utils.server import ThreadedServer
from rpyc.lib import setup_logger
from cryputils import encrypt
from cryputils import encrypt_obj
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
    class exposed_Server:
        @staticmethod
        def register_node(node_id, type_node="ds"):
            if not node_id.startswith(type_node):
                print("Unable to verify identity for", node_id)
                return -1
            nonce = random.randint(0, 100000000)
            obj = {"server": SERVER_ID, "client": node_id, "nonce": nonce}
            dcon = rpyc.connect(KDC_IP, KDC_PORT)
            serv = dcon.root.KDC()
            token = serv.get_session_key(obj)
            if token == -1:
                dcon.close()
                print("Unable to get session key")
                return -1
            decrypted_obj = decrypt_obj(token, SERVER_KEY)
            chk_node_id = decrypted_obj["id"]
            chk_nonce = int(decrypted_obj["nonce"])
            if chk_nonce != nonce or node_id != chk_node_id:
                dcon.close()
                print("Registration failed for", node_id)
                return -1
            if type_node == "ds":
                if node_id not in ds_registry:
                    ds_registry[node_id] = {}
                ds_registry[node_id]["key"] = decrypted_obj["session_key"]
            elif type_node == "fs":
                if node_id not in fs_registry:
                    fs_registry[node_id] = {}
                fs_registry[node_id]["key"] = decrypted_obj["session_key"]
            dcon.close()
            return decrypted_obj["sub_token"]

        @staticmethod
        def nonce_handshake(node_id, enc_nonce, type_node="ds"):
            if type_node == "ds":
                if node_id not in ds_registry:
                    print("Nonce Handshake Failed for", node_id)
                    return -1
                session_key = ds_registry[node_id]["key"]
            elif type_node == "fs":
                if node_id not in fs_registry:
                    print("Nonce Handshake Failed for", node_id)
                    return -1
                session_key = fs_registry[node_id]["key"]
            dec_nonce = decrypt(session_key, enc_nonce, False)
            dec_nonce = int(dec_nonce) - 1
            snd_nonce = encrypt(session_key, str(dec_nonce), False)
            return snd_nonce

        @staticmethod
        def register_port_and_ip(node_id, node_type, obj):
            if node_type == "fs" and node_id not in fs_registry:
                return False
            if node_type == "ds" and node_id not in ds_registry:
                return False
            if node_type == "ds":
                dec_obj = decrypt_obj(obj, ds_registry[node_id]["key"], False)
            if node_type == "fs":
                dec_obj = decrypt_obj(obj, fs_registry[node_id]["key"], False)
            node_port = dec_obj["port"]
            node_ip = dec_obj["ip"]
            if node_type == "fs":
                fs_registry[node_id]["port"] = node_port
                fs_registry[node_id]["ip"] = node_ip
            if node_type == "ds":
                ds_registry[node_id]["port"] = node_port
                ds_registry[node_id]["ip"] = node_ip
            return True

        @staticmethod
        def list_dir(node_id, enc_dir):
            if node_id not in ds_registry:
                return -1
            if not len(fs_registry):
                return 0
            session_key = ds_registry[node_id]["key"]
            dec_dir = decrypt(session_key, enc_dir, False)
            filenames = []
            dirnames = []
            for fs in fs_registry:
                send_dir = encrypt(fs_registry[fs]["key"], dec_dir, False)
                try:
                    dcon = rpyc.connect(fs_registry[fs]["ip"], fs_registry[fs]["port"])
                    fs_server = dcon.root.FS()
                    dir_list = fs_server.dir_list(send_dir)
                    dir_list = decrypt_obj(dir_list, fs_registry[fs]["key"], False)
                    filenames += dir_list[0]
                    dirnames += dir_list[1]
                except:
                    pass
            return encrypt_obj((filenames, dirnames), session_key, False)

if __name__ == "__main__":
    t = ThreadedServer(MasterServer, hostname=IP, port=PORT, protocol_config={'allow_public_attrs': True})
    setup_logger(quiet=False, logfile=None)
    t.start()
