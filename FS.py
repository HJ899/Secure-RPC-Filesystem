import rpyc
from rpyc.utils.server import ThreadedServer
from cryputils import *
import os
from Node import Node
import socket
import FTPServer
from multiprocessing import Process
import getpass

SESSION_KEY = None
ROOT_PATH = None

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

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
                break
            return encrypt_obj((filenames, dirnames), SESSION_KEY, False)

        @staticmethod
        def mkdir(enc_dir):
            dec_dir = decrypt(SESSION_KEY, enc_dir, False)
            if dec_dir[0] == '/':
                dec_dir = dec_dir[1:]
            dir_path = os.path.join(ROOT_PATH, dec_dir)
            try:
                os.makedirs(dir_path)
            except:
                return encrypt(SESSION_KEY, "False", False)
            return encrypt(SESSION_KEY, "True", False)

        @staticmethod
        def dir_exists(enc_dir):
            dec_dir = decrypt(SESSION_KEY, enc_dir, False)
            if dec_dir[0] == '/':
                dec_dir = dec_dir[1:]
            dir_path = os.path.join(ROOT_PATH, dec_dir)
            if os.path.exists(dir_path) and os.path.isdir(dir_path):
                return encrypt(SESSION_KEY, "True", False)
            else:
                return encrypt(SESSION_KEY, "False", False)

        @staticmethod
        def file_exists(enc_dir):
            dec_dir = decrypt(SESSION_KEY, enc_dir, False)
            if dec_dir[0] == '/':
                dec_dir = dec_dir[1:]
            dir_path = os.path.join(ROOT_PATH, dec_dir)
            if os.path.exists(dir_path) and os.path.isfile(dir_path):
                return encrypt(SESSION_KEY, "True", False)
            else:
                return encrypt(SESSION_KEY, "False", False)
        
        @staticmethod
        def delete_file(enc_dir):
            dec_dir = decrypt(SESSION_KEY, enc_dir, False)
            if dec_dir[0] == '/':
                dec_dir = dec_dir[1:]
            dir_path = os.path.join(ROOT_PATH, dec_dir)
            if os.path.exists(dir_path) and os.path.isfile(dir_path):
                os.remove(dir_path)
                return encrypt(SESSION_KEY, "True", False)
            else:
                return encrypt(SESSION_KEY, "False", False)
        
        @staticmethod
        def get_file_count():
            total_size = 0
            for (root, dirs, files) in os.walk(ROOT_PATH):
                for i in files:
                    file_path = os.path.join(root, i)
                    total_size += os.path.getsize(file_path)
            return encrypt(SESSION_KEY, str(total_size), False)

if __name__ == "__main__":
    id = input("Enter your id: ")
    pwd = getpass.getpass('Password: ')
    port = int(input("Enter port: "))
    while is_port_in_use(port) or is_port_in_use(port + 1):
        port = int(input("Ports already in use. Please enter another: "))

    node = Node(id, pwd, "fs", port=port)
    isConnect = node.connect_to_master()
    while not isConnect:
        id = input("Enter your id: ")
        pwd = getpass.getpass('Password: ')
        node.ID = id
        node.PWD = pwd
        isConnect = node.connect_to_master()
    ROOT_PATH = id + '/'
    if not os.path.exists(ROOT_PATH):
        os.mkdir(ROOT_PATH)
    SESSION_KEY = node.session_key
    home_dir = os.path.join(os.getcwd(), ROOT_PATH)
    t = ThreadedServer(FSServer, hostname="127.0.0.1", port=port, protocol_config={'allow_public_attrs': True})
    p = Process(target=FTPServer.start_server, args=(home_dir, port + 1,))
    p.daemon = True
    p.start()
    t.start()
