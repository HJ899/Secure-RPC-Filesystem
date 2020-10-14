from Node import Node
from cryputils import decrypt_obj
from cryputils import encrypt
import rpyc
from rpyc.lib import setup_logger
from rpyc.utils.server import ThreadedServer
from threading import Thread
from tabulate import tabulate

MASTER_IP = "127.0.0.1"
MASTER_PORT = 7487
MASTER_ID = "m_server"
SESSION_KEY = None


COMMANDS = ['upload', 'cat', 'cd', 'cp', 'ls', 'pwd']


class DSListener(rpyc.Service):
    @staticmethod
    def exposed_print(enc_msg):
        # dec_msg = decrypt(SESSION_KEY, enc_msg, False)
        dec_msg = enc_msg
        print(dec_msg)


class DSClient:
    def __init__(self, id, pwd):
        self.id = id
        self.pwd = pwd
        self.current_dir = '/'

    def start(self):
        dcon = rpyc.connect(MASTER_IP, MASTER_PORT)
        master = dcon.root.Server()
        while master:
            command = input("Enter your command: ")
            command = command.split(' ')
            if command[0] in COMMANDS:
                if command[0] == 'ls':
                    enc_dir = encrypt(SESSION_KEY, self.current_dir, False)
                    dir_list = master.list_dir(self.id, enc_dir)
                    dir_list = decrypt_obj(dir_list, SESSION_KEY, False)
                    tot_len = len(dir_list[0]) + len(dir_list[1])
                    if tot_len == 0:
                        print("Directory Empty!!")
                    else:
                        table = []
                        for dir_name in dir_list[1]:
                            table.append([dir_name, "--dir"])
                        for file_name in dir_list[0]:
                            table.append([file_name, "--file"])
                        print("\n", tabulate(table, headers=["name", "type"]), "\n", sep='')

                if command[0] == 'pwd':
                    print("\nPresent Directory: " + self.current_dir + "\n")

            else:
                print("Please enter a valid command")


if __name__ == "__main__":
    id = input("Enter your id: ")
    pwd = input("Enter your pwd: ")
    port = int(input("Enter port: "))
    node = Node(id, pwd, "ds", port=port)
    t1 = ThreadedServer(DSListener, hostname="127.0.0.1", port=port, protocol_config={'allow_public_attrs': True})
    t2 = DSClient(id, pwd)
    srvr = Thread(target=t1.start)
    srvr.setDaemon(True)
    srvr.start()
    isConnect = node.connect_to_master()
    while not isConnect:
        id = input("Enter your id: ")
        pwd = input("Enter your pwd: ")
        node.ID = id
        node.PWD = pwd
        isConnect = node.connect_to_master()
    SESSION_KEY = node.session_key
    t2.start()

