import os
from Node import Node
from cryputils import *
import rpyc
from rpyc.lib import setup_logger
from rpyc.utils.server import ThreadedServer
from threading import Thread
from tabulate import tabulate
import socket
import tempfile
import ftplib
import getpass
import sys

MASTER_IP = "127.0.0.1"
MASTER_PORT = 7487
MASTER_ID = "m_server"
SESSION_KEY = None

COMMANDS = ['upload', 'cat', 'cd', 'cp', 'ls', 'pwd', 'clear', 'mkdir', 'delete', 'download', 'exit', 'help']
global IS_WAITING
global WAITING_TEXT

def is_port_in_use(port_num):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port_num)) == 0

def parse_dir(parse_path: str):
    split_string = parse_path.split('/')
    split_string = [x for x in split_string if x]
    stack = []
    for item in split_string:
        if item != '.' and item != '..':
            stack.append(item)
        elif item == '..':
            if len(stack) > 0:
                stack.pop()
            else:
                return -1
    return '/' + '/'.join(stack)

def read_ftp_file(ftp: ftplib.FTP, file_path):
    temp = tempfile.TemporaryFile()
    try:
        print("Starting file read...", file_path)
        ftp.retrbinary("RETR " + file_path, temp.write, 1024)
        temp.seek(0)
        file_contents = temp.read()
        temp.close()
        return file_contents
    except ftplib.all_errors as error:
        temp.close()
        print()
        print(error)
        return -1

def download_ftp_file(ftp: ftplib.FTP, file_path):
    try:
        print("Starting file download...", file_path)
        file_name = file_path.split('/')[-1]
        if not os.path.exists('ds_files'):
            os.mkdir('ds_files')
        new_file_path = os.path.join('ds_files', file_name)
        with open(new_file_path, 'wb') as f:
            ftp.retrbinary("RETR " + file_path, f.write, 1024)
        return 200
    except ftplib.all_errors as error:
        print()
        print(error)
        return -1

def upload_ftp_file(ftp: ftplib.FTP, file_path, current_dir):
    try:
        print("Uploading file...")
        # print(file_path, current_dir)
        # print(ftp.pwd())
        # print(ftp.dir())
        save_dir = os.path.join(current_dir[1:], file_path.split('/')[-1])
        #print(save_dir)
        ftp.storbinary("STOR "+ save_dir, open(file_path, 'rb'))
        return 200
    except ftplib.all_errors as error:
        print(error)
        return -1

def cp_ftp_file(ftp_source: ftplib.FTP, source_path, ftp_dest: ftplib.FTP, dest_path, new_file_name):
    temp = tempfile.TemporaryFile()
    try:
        ftp_source.retrbinary("RETR " + source_path[1:], temp.write, 1024)
        temp.seek(0)
        write_dir = os.path.join(dest_path[1:], new_file_name)
        ftp_dest.storbinary("STOR " + write_dir, temp)
        temp.close()
        return 200

    except ftplib.all_errors as error:
        temp.close()
        print(error)
        return -1

class DSListener(rpyc.Service):
    @staticmethod
    def exposed_print(enc_msg):
        dec_msg = decrypt(SESSION_KEY, enc_msg, False)
        print('\n' + ('\n' if IS_WAITING else '') + dec_msg + "\n")
        if IS_WAITING:
            print(WAITING_TEXT, end='')
            sys.stdout.flush()

class DSClient:
    def __init__(self, id, pwd):
        self.id = id
        self.pwd = pwd
        self.current_dir = '/'

    def do_ftp(self, ftp_host, ftp_port, file_path, option, args = None):
        # options: -
        # 1. Copy
        # 2. Upload
        # 3. Read (cat)
        # 4. Download
        try:
            ftp = ftplib.FTP('')
            ftp.connect(ftp_host, ftp_port)
            ftp.login(self.id, self.pwd)
            #print("FTP PWD", ftp.pwd())
            #print("FTP DIR", ftp.dir())
            if option == 3:
                file_contents = read_ftp_file(ftp, file_path)
                if file_contents == -1:
                    return -1
                return file_contents
            elif option == 2:
                result = upload_ftp_file(ftp, file_path, self.current_dir)
                if result == -1:
                    return -1
                return 200
            elif option == 1:
                ftp_source = ftp
                if (ftp_host, ftp_port) != args[:2]:
                    ftp_source = ftplib.FTP('')
                    ftp_source.connect(args[0], args[1])
                    ftp_source.login(self.id, self.pwd)
                result = cp_ftp_file(ftp_source, args[2], ftp, file_path, args[3])
                if result == -1:
                    return -1
                return 200
            elif option == 4:
                result = download_ftp_file(ftp, file_path)
                if result == -1:
                    return -1
                return 200
        except ftplib.all_errors as error:
            print(error)
            return -1

    def start(self):
        dcon = rpyc.connect(MASTER_IP, MASTER_PORT)
        master = dcon.root.Server()
        while master:
            global IS_WAITING
            IS_WAITING = True
            global WAITING_TEXT
            WAITING_TEXT = "Enter your command: "
            command = input("Enter your command: ")
            IS_WAITING = False
            WAITING_TEXT = None
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

                elif command[0] == 'pwd':
                    print("\nPresent Directory: " + self.current_dir + "\n")
                elif command[0] == 'cd':
                    if len(command) == 1:
                        print("\ncd requires an argument -- the directory to change to\n")
                    else:
                        cd_dir = command[1]
                        if cd_dir[0] != "/":
                            cd_dir = os.path.join(self.current_dir, cd_dir)
                            # print(cd_dir)
                        cd_dir = parse_dir(cd_dir)
                        if cd_dir == -1:
                            print("\nPlease enter a valid path\n")
                            continue
                        enc_dir = encrypt(SESSION_KEY, cd_dir, False)
                        dir_exists = master.change_dir(self.id, enc_dir)
                        dir_exists = decrypt(SESSION_KEY, dir_exists, False)
                        if dir_exists == "True":
                            self.current_dir = cd_dir
                            print("\nCurrent working directory changed to: ", self.current_dir, '\n', sep='')
                        else:
                            print("\nNo such file or directory\n")
                elif command[0] == 'cat':
                    if len(command) == 1:
                        print("\nusage: cat <path-of-file-to-show>\n")
                    else:
                        file_path = command[1]
                        if file_path[0] != "/":
                            file_path = os.path.join(self.current_dir, file_path)
                        parsed_path = parse_dir(file_path)
                        if parsed_path == -1:
                            print("\nPath not valid\n")
                            continue
                        enc_path = encrypt(SESSION_KEY, parsed_path, False)
                        file_exists = master.cat_file(self.id, enc_path)
                        if not file_exists:
                            print("\nNo such file exists\n")
                        elif file_exists == -2:
                            print("\nNode not registered with Server\n")
                        else:
                            dec_obj = decrypt_obj(file_exists, SESSION_KEY, False)
                            ftp_ip, ftp_port = dec_obj
                            display_contents = self.do_ftp(ftp_ip, ftp_port, file_path, 3)
                            if display_contents != -1:
                                if isinstance(display_contents, bytes):
                                    display_contents = display_contents.decode('latin-1')
                                if not display_contents:
                                    print("\nThe file is empty\n")
                                else:
                                    print("\n" + display_contents + "\n")
                            else:
                                print("\nError occurred during FTP\n")
                elif command[0] == 'upload':
                    print('\nFiles on your system:')
                    client_path = 'ds_files'
                    client_files = os.listdir(client_path)

                    for file in client_files:
                        print(file)
                    print()
                    IS_WAITING = True
                    WAITING_TEXT = 'Enter file name to upload to current directory - ' + self.current_dir + ' : '
                    filename = input('Enter file name to upload to current directory - ' + self.current_dir + ' : ')
                    if filename == 'clear' or filename == 'exit' or filename == 'quit':
                        print()
                        IS_WAITING = False
                        WAITING_TEXT = None
                        continue
                    
                    while filename not in client_files:
                        WAITING_TEXT = 'File not found, please enter a valid file name: '
                        filename = input('File not found, please enter a valid file name: ')
                    IS_WAITING = False
                    WAITING_TEXT = None
                    client_file_path = os.path.join(client_path, filename)
                    enc_data = encrypt(SESSION_KEY, os.path.join(self.current_dir, filename), False)
                    enc_ip_port = master.get_server_to_upload_to(self.id, enc_data)
                    ftp_ip, ftp_port = decrypt_obj(enc_ip_port, SESSION_KEY, False)
                    ftp_result = self.do_ftp(ftp_ip, ftp_port, client_file_path, 2)
                    if ftp_result != -1:
                        print('\n' + filename, " successfully uploaded to", self.current_dir + '\n')
                        enc_path = encrypt(SESSION_KEY, os.path.join(self.current_dir, filename), False)
                        _ = master.notify_all_clients(self.id, enc_path)
                    else:
                        print("\nError occurred during FTP\n")
                elif command[0] == 'cp':
                    if len(command) < 3:
                        print('\nusage: cp <path-of-file-to-copy> <destination-path>\n')
                    else:
                        source = command[1]
                        if source[0] != '/':
                            source = os.path.join(self.current_dir, source)
                        source = parse_dir(source)
                        if source == -1:
                            print('\nEnter Valid Source Path\n')
                            continue
                        destination = command[2]
                        if destination[0] != '/':
                            destination = os.path.join(self.current_dir, destination)
                        destination = parse_dir(destination)
                        if destination == -1:
                            print('\nEnter Valid Destination Path\n')
                            continue
                        enc_paths = encrypt_obj((source, destination), SESSION_KEY, False)
                        enc_ftp_creds = master.get_cp_ftp_creds(self.id, enc_paths)
                        if not enc_ftp_creds:
                            print('\nSource or Destination Path invalid.\n')
                            continue
                        ip_source, port_source, ip_dest, port_dest, new_file_name = decrypt_obj(enc_ftp_creds, SESSION_KEY, False)
                        ftp_result = self.do_ftp(ip_dest, port_dest, destination, 1, (ip_source, port_source, source, new_file_name))
                        if ftp_result == -1:
                            print('\nServer Error During Copying...Try again later\n')
                        else:
                            print('\nSuccesfully copied file to', destination + '\n')
                elif command[0] == 'download':
                    if len(command) == 1:
                        print("\ndownload requires an argument -- the file to display\n")
                    else:
                        file_path = command[1]
                        if file_path[0] != "/":
                            file_path = os.path.join(self.current_dir, file_path)
                        parsed_path = parse_dir(file_path)
                        if parsed_path == -1:
                            print("\nPath not valid\n")
                            continue
                        enc_path = encrypt(SESSION_KEY, parsed_path, False)
                        file_exists = master.cat_file(self.id, enc_path)
                        if not file_exists:
                            print("\nNo such file exists\n")
                        elif file_exists == -2:
                            print("\nNode not registered with Server\n")
                        else:
                            dec_obj = decrypt_obj(file_exists, SESSION_KEY, False)
                            ftp_ip, ftp_port = dec_obj
                            display_contents = self.do_ftp(ftp_ip, ftp_port, file_path, 4)
                            if display_contents != -1:
                                print("\nFile Download Successful!\n")
                            else:
                                print("\nError occurred during FTP\n")
                elif command[0] == 'mkdir':
                    if len(command) < 2:
                        print("\nmkdir requires an argument -- the folder to create\n")
                    else:
                        folder_name = command[1]
                        if folder_name[0] != "/":
                            folder_name = os.path.join(self.current_dir, folder_name)
                        parsed_path = parse_dir(folder_name)
                        if parsed_path == -1:
                            print("\nInvalid Name\n")
                            continue
                        enc_folder = encrypt(SESSION_KEY, parsed_path, False)
                        enc_ret = master.mkdir(self.id, enc_folder)
                        dec_ret = decrypt(SESSION_KEY, enc_ret, False)
                        if dec_ret == "True":
                            print("\nFolder created successfully\n")
                        else:
                            print("\nUnable to create folder\n")
                elif command[0] == 'delete':
                    if len(command) < 2:
                        print("\nUsage: delete <path_to_file>\n")
                        continue
                    else:
                        file_path = command[1]
                        if file_path[0] != '/':
                            file_path = os.path.join(self.current_dir, file_path)
                        file_path = parse_dir(file_path)
                        enc_path = encrypt(SESSION_KEY, file_path, False)
                        ret = master.delete_file(self.id, enc_path)
                        if ret != False:
                            print('\nDeleted Successfully!\n')
                        else:
                            print('\nEnter Valid File Path\n')
                elif command[0] == "clear":
                    os.system('clear')
                elif command[0] == "help":
                    print("\nThe Following commands are available: -\n")
                    print("pwd: List the present working directory")
                    print("args: none\n")
                    print("ls: Lists the contents of current directory")
                    print("args: none\n")
                    print("cp: copy one file to another")
                    print("args: <path-of-file-to-copy> <destination-path>\n")
                    print("cat: display contents of a file")
                    print("args: <path-of-file-to-show>\n")
                    print("cd: change current directory")
                    print("args: <directory-to-change-to>\n")
                    print("download: download a file")
                    print("args: <path-of-file-to-download>\n")
                    print("upload: upload a file")
                    print("args: none\n")
                    print("mkdir: create a directory")
                    print("args: <name-of-directory-to-create>\n")
                    print("delete: delete a file")
                    print("args: <path-of-file-to-delete>\n")
                    print("clear: clear console")
                    print("args: none\n")
                    print("exit: exit the program")
                    print("args: none\n")
                    print("help: show help")
                    print("args: none\n")
                elif command[0] == 'exit':
                    break
            else:
                print("\nPlease enter a valid command\n")


if __name__ == "__main__":
    id = input("Enter your id: ")
    pwd = getpass.getpass('Password: ')
    port = int(input("Enter port: "))
    while is_port_in_use(port):
        port = int(input("Port already in use. Please enter another: "))

    node = Node(id, pwd, "ds", port=port)
    t1 = ThreadedServer(DSListener, hostname="127.0.0.1", port=port, protocol_config={'allow_public_attrs': True})
    t2 = DSClient(id, pwd)
    srvr = Thread(target=t1.start)
    srvr.setDaemon(True)
    srvr.start()
    isConnect = node.connect_to_master()
    while not isConnect:
        id = input("Enter your id: ")
        pwd = getpass.getpass('Password: ')
        node.ID = id
        node.PWD = pwd
        isConnect = node.connect_to_master()
    IS_WAITING = True
    SESSION_KEY = node.session_key
    t2.start()
