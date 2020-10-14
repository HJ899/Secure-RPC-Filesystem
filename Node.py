import random
import rpyc
from cryputils import decrypt_obj
from cryputils import decrypt
from cryputils import encrypt
from cryputils import encrypt_obj

MASTER_IP = "127.0.0.1"
MASTER_PORT = 7487
MASTER_ID = "m_server"


class Node:
    def __init__(self, id="ds_1", pwd="pwd1", node_type="ds", ip="127.0.0.1", port=38913):
        self.ID = id
        self.PWD = pwd
        self.master = None
        self.session_key = None
        self.type = node_type
        self.ip = ip
        self.port = port

    def connect_to_master(self):
        dcon = rpyc.connect(MASTER_IP, MASTER_PORT)
        self.master = dcon.root.Server()
        poss_key = self.register_with_master()
        if poss_key == -1:
            dcon.close()
            self.master = None
            return False
        self.session_key = poss_key
        print("Session Key Obtained")
        success = self.nonce_handshake()
        if not success:
            print("Nonce Handshake Failed, Please Re-Login")
            self.session_key = None
            dcon.close()
            self.master = None
            return False
        print("Nonce Handshake Successful")
        if not self.send_port_and_ip():
            dcon.close()
            self.master = None
            print("Port and IP not sent successfully")
            return False
        print("Port and IP sent successfully")
        dcon.close()
        self.master = None
        return True

    def nonce_handshake(self):
        nonce = random.randint(0, 100000000)
        enc_nonce = encrypt(self.session_key, str(nonce), False)
        chk_nonce = self.master.nonce_handshake(self.ID, enc_nonce, self.type)
        dec_nonce = decrypt(self.session_key, chk_nonce, False)
        dec_nonce = int(dec_nonce)
        return nonce - 1 == dec_nonce

    def register_with_master(self):
        token = self.master.register_node(self.ID, self.type)
        if token == -1:
            print("Unable to connect to master, Please check you credentials")
            return -1
        try:
            decrypted_token = decrypt_obj(token, self.PWD)
            chk_server_id = decrypted_token["id"]
        except:
            print("Unable to connect to master, Please check you credentials")
            return -1
        if chk_server_id != MASTER_ID:
            print("Authentication with server failed!")
            return -1
        return decrypted_token["session_key"]

    def send_port_and_ip(self):
        params = {"port": self.port, "ip": self.ip}
        enc_params = encrypt_obj(params, self.session_key, False)
        return self.master.register_port_and_ip(self.ID, self.type, enc_params)
