from Node import Node


class DSNode(Node):
    def __init__(self, id="ds_1", pwd="pwd1"):
        super().__init__(id, pwd, "ds")


if __name__ == "__main__":
    id = input("Enter your id: ")
    pwd = input("Enter your pwd: ")
    node = DSNode(id, pwd)
    isConnect = node.connect_to_master()
    while not isConnect:
        id = input("Enter your id: ")
        pwd = input("Enter your pwd: ")
        node.ID = id
        node.PWD = pwd
        isConnect = node.connect_to_master()

