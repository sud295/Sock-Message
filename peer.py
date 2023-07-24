import socket
from candidate import *
from message_process import *

def main():
    user_name = input("User Name: ")

    HOST = socket.gethostbyname(socket.gethostname())

    PORT = 0
    try:
        PORT = int(input("Enter Port: "))
    except:
        print("Not a valid port")
        raise SystemExit

    reverse_proxy_host = "127.0.0.1"
    reverse_proxy_port = 9001

    # Connect to the reverse proxy server
    reverse_proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    reverse_proxy_socket.connect((reverse_proxy_host, reverse_proxy_port))

    # Send leader assignment request
    reverse_proxy_socket.sendall(f"$leader${HOST}:{PORT}".encode())

    # Receive response from the reverse proxy
    response = reverse_proxy_socket.recv(1024).decode()

    reverse_proxy_socket.close()
    
    system = Message_Process(HOST, PORT, user_name)
    if response == "$yes$":
        print("$Leadership Obtained$")
        system.start_leader()

    else:
        system.start_follower(response)

if __name__ == "__main__":
    main()
