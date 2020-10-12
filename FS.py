from Node import Node


class FSNode(Node):
    def __init__(self, id, pwd):
        super().__init__(id, pwd, "fs")


if __name__ == "__main__":
    id = input("Enter your id: ")
    pwd = input("Enter your pwd: ")
    node = FSNode(id, pwd)
    isConnect = node.connect_to_master()
    while not isConnect:
        id = input("Enter your id: ")
        pwd = input("Enter your pwd: ")
        node.ID = id
        node.PWD = pwd
        isConnect = node.connect_to_master()
