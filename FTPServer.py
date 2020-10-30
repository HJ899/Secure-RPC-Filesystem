from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import ThreadedFTPServer
import json

def start_server(home_dir, port):
    host = '127.0.0.1'
    authorizer = DummyAuthorizer()
    with open('./db.json') as f:
        auth_info = json.loads(f.read())
    for user in auth_info:
        if user.startswith('ds'):
            authorizer.add_user(user, auth_info[user], homedir=home_dir, perm='elradfmw')
    handler = FTPHandler
    handler.authorizer = authorizer
    server = ThreadedFTPServer((host, port), handler)
    print("Starting FTP Server on port:", port)
    server.serve_forever()
