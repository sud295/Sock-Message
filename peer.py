import socket
from candidate import *
from message_process import *
import yaml

def main():
    with open("config.yml", "r") as f:
        config = yaml.safe_load(f)

    user_name = input("User Name: ")

    if input("Auto-generate IP? (y/n): ") == 'y':
        peer_IP = socket.gethostbyname(socket.gethostname())
    else:
        peer_IP = str(input("Specify IP: "))

    print("IP being used: " + peer_IP)

    peer_port = 0
    try:
        peer_port = int(input("Enter Port: "))
    except:
        print("Not a valid port")
        raise SystemExit

    # Connect to the reverse proxy server
    reverse_proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    reverse_proxy_host = config["reverse_proxy_host"]
    reverse_proxy_port = config["reverse_proxy_port"]
    reverse_proxy_socket.connect((reverse_proxy_host, reverse_proxy_port))

    reverse_proxy_socket.sendall(f"$leader${peer_IP}:{peer_port}".encode())

    # Receive response from the reverse proxy
    response = reverse_proxy_socket.recv(1024).decode()

    reverse_proxy_socket.close()
    
    system = Message_Process(peer_IP, peer_port, user_name)
    if response == "$yes$":
        print("$Leadership Obtained$")
        system.start_leader()

    else:
        system.start_follower(response)

if __name__ == "__main__":
    main()
