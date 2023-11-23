import socket
import select
import yaml
import json 

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.padding import MGF1, OAEP
from cryptography.hazmat.primitives import serialization, hashes

def main():
    # Open the config file for the adress to bind to
    with open("config.yml", "r") as f:
        config = yaml.safe_load(f)
    host = config["key_manager_host"]
    port = config["key_manager_port"]
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(5)

    poller = select.poll()
    poller.register(server_socket, select.POLLIN)

    connected_clients = {}

    print("Listening for connections...")

    key_map = {}

    while True:
        events = poller.poll(-1)

        for fd, event in events:
            if fd == server_socket.fileno():
                # New connection event
                client_socket, client_address = server_socket.accept()
                #print("New connection from:", client_address)

                # Register the client socket for reading
                poller.register(client_socket, select.POLLIN)
                connected_clients[client_socket.fileno()] = client_socket
            else:
                # Data received or connection closed event
                client_socket = connected_clients[fd]
                if event & select.POLLIN:
                    data = client_socket.recv(1024)
                    if data:
                        if data[:4] == b'$req':
                            # Handle requests for public keys
                            key = key_map.get(data[4:].decode())
                            if key:
                                client_socket.sendall(key)
                            else:
                                client_socket.sendall("$Error".encode())
                        else:
                            try:
                                decrypted_data = get_private_key().\
                                decrypt(data, OAEP(mgf=MGF1(algorithm=hashes.SHA256()), 
                                                   algorithm=hashes.SHA256(), label=None))

                                json_data = json.loads(decrypted_data.decode('utf-8'))

                                client_key_pem = json_data["public_key"].encode('utf-8')
                                address = json_data["address"]

                                key_map[address] = client_key_pem
                                print("Ready")
                            except:
                                print("Authentication Failed")
                    else:
                        poller.unregister(client_socket)
                        client_socket.close()
                        del connected_clients[fd]

def get_private_key():
    with open("manager_private_key.pem", "rb") as f:
        rsa_private_key_pem = f.read()
        rsa_private_key = serialization.load_pem_private_key(rsa_private_key_pem, password=None, backend=default_backend())
        return rsa_private_key

if __name__ == "__main__":
    main()