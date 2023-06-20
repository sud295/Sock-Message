import socket
import time
import threading

def message(sockfd):
    global keep_running
    while keep_running:
        time.sleep(0.3)
        message = input()
        if message == "$ exit":
            keep_running = False
        sockfd.sendall(message.encode())
    time.sleep(1)
    sockfd.close()
    raise SystemExit(0)

def recieve(sockfd):
    global keep_running
    while keep_running:
        message = sockfd.recv(4096)
        print(message.decode())

def main():
    global keep_running
    keep_running = True

    HOST = "127.0.0.1"
    PORT = 12346

    sockfd = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    sockfd.connect((HOST,PORT))

    message_thread = threading.Thread(target=message, args=(sockfd,))
    recieving_thread = threading.Thread(target=recieve, args=(sockfd,))
    message_thread.start()
    recieving_thread.start()

if __name__ == "__main__":
    main()
    