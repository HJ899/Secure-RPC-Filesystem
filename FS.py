import rpyc
from rpyc.utils.server import ThreadedServer
from cryputils import decrypt_obj
from cryputils import encrypt_obj
from cryputils import encrypt
from cryputils import decrypt
import os
from Node import Node

SESSION_KEY = None
ROOT_PATH = None


class FSServer(rpyc.Service):
    class exposed_FS:
        @staticmethod
        def dir_list(enc_dir):
            dec_dir = decrypt(SESSION_KEY, enc_dir, False)
            if dec_dir[0] == '/':
                dec_dir = dec_dir[1:]
            dir_path = os.path.join(ROOT_PATH, dec_dir)
            filenames = []
            dirnames = []
            for (main_dir, dnames, fnames) in os.walk(dir_path):
                filenames.extend(fnames)
                dirnames.extend(dnames)
            return encrypt_obj((filenames, dirnames), SESSION_KEY, False)


if __name__ == "__main__":
    id = input("Enter your id: ")
    pwd = input("Enter your pwd: ")
    port = int(input("Enter port: "))
    node = Node(id, pwd, "fs", port=port)
    isConnect = node.connect_to_master()
    while not isConnect:
        id = input("Enter your id: ")
        pwd = input("Enter your pwd: ")
        node.ID = id
        node.PWD = pwd
        isConnect = node.connect_to_master()
    ROOT_PATH = id + '/'
    if not os.path.exists(ROOT_PATH):
        os.mkdir(ROOT_PATH)
    SESSION_KEY = node.session_key
    t = ThreadedServer(FSServer, hostname="127.0.0.1", port=port, protocol_config={'allow_public_attrs': True})
    t.start()
