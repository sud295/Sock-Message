import socket
import time
import threading

def message(sockfd):
    while True:
        time.sleep(0.3)
        message = input()
        sockfd.sendall(message.encode())


def recieve(sockfd):
    while True:
        message = sockfd.recv(4096)
        print(message.decode())

HOST = "127.0.0.1"
PORT = 12346

sockfd = socket.socket(socket.AF_INET,socket.SOCK_STREAM)

sockfd.bind((HOST,PORT))
sockfd.listen(2)
client, client_addr = sockfd.accept()

message_thread = threading.Thread(target=message, args=(client,))
recieving_thread = threading.Thread(target=recieve, args=(client,))
message_thread.start()
recieving_thread.start()