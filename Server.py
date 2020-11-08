import rpyc
import random
import os
import json
from rpyc.utils.server import ThreadedServer
from rpyc.lib import setup_logger
from cryputils import *

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
                return -2
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
            filenames = list(set(filenames))
            dirnames = list(set(dirnames))
            return encrypt_obj((filenames, dirnames), session_key, False)

        @staticmethod
        def change_dir(node_id, enc_dir):
            if node_id not in ds_registry:
                return -2
            session_key = ds_registry[node_id]["key"]
            dec_dir = decrypt(session_key, enc_dir, False)
            for fs in fs_registry:
                send_dir = encrypt(fs_registry[fs]["key"], dec_dir, False)
                try:
                    dcon = rpyc.connect(fs_registry[fs]["ip"], fs_registry[fs]["port"])
                    fs_server = dcon.root.FS()
                    enc_exists = fs_server.dir_exists(send_dir)
                    dec_exists = decrypt(fs_registry[fs]["key"], enc_exists, False)
                    if dec_exists == "True":
                        return encrypt(session_key, "True", False)
                except:
                    pass
            return encrypt(session_key, "False", False)

        @staticmethod
        def mkdir(node_id, enc_folder):
            if node_id not in ds_registry:
                return -2
            session_key = ds_registry[node_id]["key"]
            folder_name = decrypt(session_key, enc_folder, False)
            is_created = False
            for fs in fs_registry:
                send_path = encrypt(fs_registry[fs]["key"], folder_name, False)
                try:
                    dcon = rpyc.connect(fs_registry[fs]["ip"], fs_registry[fs]["port"])
                    fs_server = dcon.root.FS()
                    enc_exists = fs_server.mkdir(send_path)
                    dec_exists = decrypt(fs_registry[fs]["key"], enc_exists, False)
                    if dec_exists == "True":
                        is_created = True
                except:
                    pass
            return encrypt(session_key, str(is_created), False)

        @staticmethod
        def cat_file(node_id, enc_path):
            if node_id not in ds_registry:
                return -2
            session_key = ds_registry[node_id]["key"]
            dec_path = decrypt(session_key, enc_path, False)
            for fs in fs_registry:
                send_path = encrypt(fs_registry[fs]["key"], dec_path, False)
                try:
                    dcon = rpyc.connect(fs_registry[fs]["ip"], fs_registry[fs]["port"])
                    fs_server = dcon.root.FS()
                    enc_path_exists = fs_server.file_exists(send_path)
                    dec_exists = decrypt(fs_registry[fs]["key"], enc_path_exists, False)
                    if dec_exists == "True":
                        port_ftp = int(fs_registry[fs]["port"]) + 1
                        ip_ftp = fs_registry[fs]["ip"]
                        return encrypt_obj((ip_ftp, port_ftp), session_key, False)
                except:
                    pass
            return False

        @staticmethod
        def get_server_to_upload_to(node_id, enc_path):
            if node_id not in ds_registry:
                return -2
            session_key = ds_registry[node_id]["key"] 
            dec_path = decrypt(session_key, enc_path, False)
            file_counts = {}

            for fs in fs_registry:
                send_path = encrypt(fs_registry[fs]["key"], dec_path, False)
                try:
                    dcon = rpyc.connect(fs_registry[fs]["ip"], fs_registry[fs]["port"])
                    fs_server = dcon.root.FS()

                    enc_file_count = fs_server.get_file_count()
                    file_count = int(decrypt(fs_registry[fs]["key"], enc_file_count, False))
                    file_counts[fs] = file_count

                    enc_file_exists = fs_server.file_exists(send_path)
                    file_exists = decrypt(fs_registry[fs]["key"], enc_file_exists, False)
                    if file_exists == "True":
                        port_ftp = int(fs_registry[fs]["port"]) + 1
                        ip_ftp = fs_registry[fs]["ip"]
                        return encrypt_obj((ip_ftp, port_ftp), session_key, False)
                except:
                    pass
            
            sorted_file_counts = sorted(file_counts.items(), key=lambda kv: kv[1])
            print(sorted_file_counts)
            fs = sorted_file_counts[0][0]
            send_path = '/'.join(dec_path.split('/')[:-1])
            if send_path != '':
                send_path = encrypt(fs_registry[fs]["key"], send_path, False)
                try:
                    dcon = rpyc.connect(fs_registry[fs]["ip"], fs_registry[fs]["port"])
                    fs_server = dcon.root.FS()
                    _ = fs_server.mkdir(send_path)
                except:
                    pass
            port_ftp = int(fs_registry[fs]["port"]) + 1
            ip_ftp = fs_registry[fs]["ip"]
            return encrypt_obj((ip_ftp, port_ftp), session_key, False)
        
        @staticmethod
        def get_cp_ftp_creds(node_id, enc_paths):
            if node_id not in ds_registry:
                return -2
            session_key = ds_registry[node_id]["key"]
            source, dest = decrypt_obj(enc_paths, session_key, False)

            source_ip = None
            source_port = None
            dest_ip = None
            dest_port = None
            new_file_name = None

            for fs in fs_registry:
                send_path = encrypt(fs_registry[fs]["key"], source, False)
                try:
                    dcon = rpyc.connect(fs_registry[fs]["ip"], fs_registry[fs]["port"])
                    fs_server = dcon.root.FS()
                    enc_path_exists = fs_server.file_exists(send_path)
                    dec_exists = decrypt(fs_registry[fs]["key"], enc_path_exists, False)
                    if dec_exists == "True":
                        source_port = int(fs_registry[fs]["port"]) + 1
                        source_ip = fs_registry[fs]["ip"]
                        break
                except:
                    pass
            
            if source_ip == None:
                return False
            
            file_name = source.split('/')[-1]
            new_file_name = file_name
            dest_file_if_exists = os.path.join(dest, file_name)
            file_counts = {}
            files_in_destination_path = []

            for fs in fs_registry:
                send_path = encrypt(fs_registry[fs]["key"], dest_file_if_exists, False)
                enc_dest_path = encrypt(fs_registry[fs]["key"], dest, False)
                try:
                    dcon = rpyc.connect(fs_registry[fs]["ip"], fs_registry[fs]["port"])
                    fs_server = dcon.root.FS()

                    enc_file_count = fs_server.get_file_count()
                    file_count = int(decrypt(fs_registry[fs]["key"], enc_file_count, False))
                    file_counts[fs] = file_count

                    enc_filenames_in_dest = fs_server.dir_list(enc_dest_path)
                    filenames_in_dest = decrypt_obj(enc_filenames_in_dest, fs_registry[fs]["key"], False)[0]
                    files_in_destination_path.extend(filenames_in_dest) 
                    
                    # enc_file_exists = fs_server.file_exists(send_path)
                    # file_exists = decrypt(fs_registry[fs]["key"], enc_file_exists, False)
                    # if file_exists == "True":
                    #     dest_port = int(fs_registry[fs]["port"]) + 1
                    #     dest_ip = fs_registry[fs]["ip"]
                    #     break
                except:
                    pass
            
            if dest_ip == None:
                sorted_file_counts = sorted(file_counts.items(), key=lambda kv: kv[1])
                fs = sorted_file_counts[0][0]
                send_path = encrypt(fs_registry[fs]["key"], dest, False)
                try:
                    dcon = rpyc.connect(fs_registry[fs]["ip"], fs_registry[fs]["port"])
                    fs_server = dcon.root.FS()
                    _ = fs_server.mkdir(send_path)
                except:
                    pass
                dest_port = int(fs_registry[fs]["port"]) + 1
                dest_ip = fs_registry[fs]["ip"]
            
            if new_file_name in files_in_destination_path:
                f_name = '.'.join(new_file_name.split('.')[:-1])
                ext = '.' + new_file_name.split('.')[-1]
                for i in range(1,10000):
                    if f_name + '_copy_' + str(i) + ext not in files_in_destination_path:
                        new_file_name = f_name + '_copy_' + str(i) + ext
                        break

            return encrypt_obj((source_ip, source_port, dest_ip, dest_port, new_file_name), session_key, False)

        @staticmethod
        def notify_all_clients(node_id, enc_path):
            if node_id not in ds_registry:
                return -2
            session_key = ds_registry[node_id]["key"]
            dec_path = decrypt(session_key, enc_path, False)

            for ds in ds_registry:
                if ds != node_id:
                    try:
                        dcon = rpyc.connect(ds_registry[ds]["ip"], ds_registry[ds]["port"])
                        message = "new File Uploaded: " + dec_path + " | by " + node_id
                        enc_message = encrypt(ds_registry[ds]["key"], message, False)
                        dcon.root.print(enc_message)
                    except:
                        pass
            return True

        @staticmethod
        def delete_file(node_id, enc_path):
            if node_id not in ds_registry:
                return -2
            session_key = ds_registry[node_id]["key"]
            dec_path = decrypt(session_key, enc_path, False)
            for fs in fs_registry:
                send_path = encrypt(fs_registry[fs]["key"], dec_path, False)
                try:
                    dcon = rpyc.connect(fs_registry[fs]["ip"], fs_registry[fs]["port"])
                    fs_server = dcon.root.FS()
                    ret = fs_server.delete_file(send_path)
                    dec_exists = decrypt(fs_registry[fs]["key"], ret, False)
                    if dec_exists == "True":
                        return encrypt(session_key, "True", False)
                except:
                    pass
            return False

if __name__ == "__main__":
    t = ThreadedServer(MasterServer, hostname=IP, port=PORT, protocol_config={'allow_public_attrs': True})
    setup_logger(quiet=False, logfile=None)
    t.start()