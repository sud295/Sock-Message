import socket
import select
import threading
import time

def leader_thread(event):
    print("$Leader Thread Started$")
    global network_participants
    network_participants = []
    prev_participants = network_participants
    participant_sockets = []

    while not event.is_set():
        time.sleep(1.5)
        message = "$HEARTBEAT$"
        for participant in network_participants:
            message += participant
            message += ","
        message = message[:-1]

        if prev_participants != network_participants:
            new_participants = set(network_participants) - set(prev_participants)
            closed_sockets = []

            for participant in new_participants:
                participant_IP, participant_port = participant.split(":")
                participant_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    participant_socket.connect((participant_IP, int(participant_port)))
                    participant_sockets.append(participant_socket)
                except:
                    continue

            for participant_socket in participant_sockets:
                try:
                    participant_socket.sendall(message.encode())
                except:
                    closed_sockets.append(participant_socket)
                    continue

            for closed_socket in closed_sockets:
                participant_sockets.remove(closed_socket)

            prev_participants = network_participants
        else:
            for participant_socket in participant_sockets:
                try:
                    participant_socket.sendall(message.encode())
                except:
                    participant_sockets.remove(participant_socket)
                    continue

        print("$Sent Heartbeat$")
    
def send_thread(event):
    print("$Send Thread Started$")
    global network_participants
    network_participants = []
    prev_participants = network_participants
    participant_sockets = []

    while not event.is_set():
        message = input("Enter message: ")

        if message == "$exit":
            event.set()
            break
        
        if prev_participants != network_participants:
            new_participants = set(network_participants) - set(prev_participants)
            closed_sockets = []
            
            for participant in new_participants:
                participant_IP, participant_port = participant.split(":")
                participant_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    participant_socket.connect((participant_IP, int(participant_port)))
                    participant_sockets.append(participant_socket)
                except:
                    continue

            for participant_socket in participant_sockets:
                try:
                    participant_socket.sendall(message.encode())
                except:
                    closed_sockets.append(participant_socket)
                    continue
            
            for closed_socket in closed_sockets:
                participant_sockets.remove(closed_socket)
                closed_socket.close()

            prev_participants = network_participants
        else:
            for participant_socket in participant_sockets:
                try:
                    participant_socket.sendall(message.encode())
                except:
                    participant_sockets.remove(participant_socket)
                    participant_socket.close()
                    continue

    
def receive_thread(server_socket, event):
    print("$Receive Thread Started$")
    global network_participants
    network_participants = []
    connected_clients = {}
    client_sockets = []
    poller = select.poll()

    poller.register(server_socket, select.POLLIN)

    last_heartbeat_time = time.time()
    while not event.is_set():
        try:
            events = poller.poll(-1)

            for fd, ev in events:
                if fd == server_socket.fileno():
                    # New connection event
                    client_socket, client_address = server_socket.accept()
                    print("New connection from:", client_address)

                    # Register the client socket for reading
                    poller.register(client_socket, select.POLLIN)
                    connected_clients[client_socket.fileno()] = client_socket
                    client_sockets.append(client_socket)
                else:
                    client_socket = connected_clients[fd]
                    if ev & select.POLLIN:
                        data = client_socket.recv(4096).decode()
                        if data:
                            # For the leader to add all participant IPs
                            if "$addr$" in data and leader == True:
                                network_participants.append(data[6:])
                                print(network_participants)
                            # For the follower to receive heartbeats
                            elif "$HEARTBEAT$" in data and leader == False:
                                if time.time() - last_heartbeat_time >= 4:
                                    print("Leader died")
                                heartbeat = data[11:]
                                print(heartbeat)
                                # Split the heartbeat into individual participants
                                heartbeat_participants = heartbeat.split(",")
                                # Filter out the current follower's IP and port
                                filtered_participants = [
                                    participant for participant in heartbeat_participants
                                    if participant != f"{HOST}:{PORT}"
                                ]
                                network_participants = filtered_participants
                                last_heartbeat_time = time.time()
                            else:
                                print(f"{client_socket.getpeername()}: {data}")
                        else:
                            print(f"{client_socket.getpeername()} Left the Chat")
                            poller.unregister(client_socket)
                            client_socket.close()
                            del connected_clients[fd]
                            client_sockets.remove(client_socket)
        except select.error:
            continue

    # Close all client sockets
    for client_socket in client_sockets:
        client_socket.close()

def main():
    global leader
    leader = False

    event = threading.Event()

    global HOST
    HOST = "127.0.0.1"

    global PORT
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

    if response == "$yes$":
        reverse_proxy_socket.close()
        leader = True
        print("$Leadership Obtained$")
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)

        lead = threading.Thread(target=leader_thread, args=(event,))
        inp = threading.Thread(target=receive_thread, args=(server_socket, event,))
        out = threading.Thread(target=send_thread, args=(event,))

        lead.start()
        inp.start()
        out.start()

        lead.join()
        inp.join()
        out.join()

    else:
        reverse_proxy_socket.close()
        leader_IP, leader_port = response.split(":")

        leader_port = int(leader_port)
        
        print(leader_IP, leader_port)
        leader_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        leader_socket.connect((leader_IP, leader_port))
        leader_socket.sendall(f"$addr${HOST}:{PORT}".encode())

        leader_socket.close()

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)

        inp = threading.Thread(target=receive_thread, args=(server_socket, event,))
        out = threading.Thread(target=send_thread, args=(event,))

        inp.start()
        out.start()

        inp.join()
        out.join()

if __name__ == "__main__":
    main()
