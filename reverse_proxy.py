import socket
import select
import yaml

def main():
    with open("config.yml", "r") as f:
        config = yaml.safe_load(f)
    reverse_proxy_host = config["reverse_proxy_host"]
    reverse_proxy_port = config["reverse_proxy_port"]
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((reverse_proxy_host, reverse_proxy_port))
    server_socket.listen(5)

    poller = select.poll()
    poller.register(server_socket, select.POLLIN)

    connected_clients = {}

    print("Listening for connections...")

    leader_assigned = False
    leader_IP = ""
    leader_port = 0

    while True:
        events = poller.poll(-1)

        for fd, event in events:
            if fd == server_socket.fileno():
                # New connection event
                client_socket, client_address = server_socket.accept()
                print("New connection from:", client_address)

                # Register the client socket for reading
                poller.register(client_socket, select.POLLIN)
                connected_clients[client_socket.fileno()] = client_socket
            else:
                # Data received or connection closed event
                client_socket = connected_clients[fd]
                if event & select.POLLIN:
                    # Handle data from the client
                    data = client_socket.recv(1024).decode()
                    if data:
                        print("Received data:", data)
                        if '$leader$' in data and not leader_assigned:
                            client_socket.sendall('$yes$'.encode())
                            data = data[8:]
                            data = data.split(':')
                            leader_IP = data[0]
                            leader_port = data[1]
                            leader_assigned = True
                        elif '$leader$' in data and leader_assigned:
                            client_socket.sendall(f'{leader_IP}:{leader_port}'.encode())
                        # for re-election where consensus is reached internally
                        elif '$FORCE leader$' in data:
                            data = data[14:]
                            data = data.split(':')
                            leader_IP = data[0]
                            leader_port = data[1]
                            leader_assigned = True
                            print("Leader Updated")
                    else:
                        # Connection closed by the client
                        print("Connection closed:", client_socket.getpeername())
                        poller.unregister(client_socket)
                        client_socket.close()
                        del connected_clients[fd]

if __name__ == "__main__":
    main()