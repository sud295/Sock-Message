import socket
import select
import threading
import time
import copy
import os
from candidate import Candidate

def leader_thread(event, net_part: list) -> None:
    '''
    This function outlies the unique tasks of a leader peer
    The leader sends heartbeats at regular intervals of 1.5 seconds
    These heartbeat messages contain the adresses of the receiving ends of all network participants
    The leader uses its own port for communicating with the followers so as to not get mixed with the other messages
    '''

    # When a new leader is elected, it will broadcast its adress for the followers to note
    broadcast_addr = False

    '''
    Since the innitial election process and the re-election processes are different, there is a distinction between 
    being a leader and being a new leader
    '''
    global new_leader
    global network_participants
    global HOST
    global PORT

    network_participants = copy.deepcopy(net_part)

    global participant_dict
    participant_dict = {}

    # As long as the user does not type $exit
    while not event.is_set():
        time.sleep(1.5)
        message = "$HEARTBEAT$"
        for participant in network_participants:
            message += participant
            message += ","
        message = message[:-1]

        for participant in network_participants:
            sock = participant_dict.get(participant)
            if sock == None:
                participant_IP, participant_port = participant.split(":")
                participant_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    participant_socket.connect((participant_IP, int(participant_port)))
                except:
                    print(f"Could not add new participant {participant_IP}:{participant_port}")
                    network_participants.remove(participant)  
                    continue
                participant_dict[participant] = participant_socket
                sock = participant_dict.get(participant)
            try:
                sock.sendall(message.encode())
            except:
                network_participants.remove(participant)
                participant_dict[participant] = None

        if not broadcast_addr and new_leader:
            message = f"$FORCE leader${HOST}:{PORT}".encode()
            for participant in network_participants:
                sock = participant_dict.get(participant)
                if sock == None:
                    participant_IP, participant_port = participant.split(":")
                    participant_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    try:
                        participant_socket.connect((participant_IP, int(participant_port)))
                    except:
                        print(f"Could not add new participant {participant_IP}:{participant_port}")
                        network_participants.remove(participant)  
                        continue
                    participant_dict[participant] = participant_socket
                    sock = participant_dict.get(participant)
                try:
                    sock.sendall(message.encode())
                except:
                    network_participants.remove(participant)
                    participant_dict[participant] = None
            broadcast_addr = True

        print(message)

def send_thread(event) -> None:
    global network_participants
    network_participants = []
    global leader_socket
    global participant_dict

    while not event.is_set():
        message = input("")

        if message == "$exit":
            event.set()
            break
        
        if not leader:
            try:
                leader_socket.sendall(message.encode())
            except:
                pass
            
        for participant in network_participants:
            sock = participant_dict.get(participant)
            if sock == None:
                participant_IP, participant_port = participant.split(":")
                participant_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    participant_socket.connect((participant_IP, int(participant_port)))
                except:
                    print(f"Could not add new participant {participant_IP}:{participant_port}")
                    network_participants.remove(participant)  
                    continue
                participant_dict[participant] = participant_socket
                sock = participant_dict.get(participant)
            try:
                sock.sendall(message.encode())
            except:
                network_participants.remove(participant)
                participant_dict[participant] = None

def timer_thread(event) -> None:
    global election_ongoing
    election_ongoing = False

    global leader_socket

    global recieved
    recieved = False
    index = 0
    while not event.is_set() and not leader:
        if recieved:
            recieved = False
            index = 0
        time.sleep(1)
        index += 1
        if index > 3:
            if not election_ongoing and not leader:
                leader_socket.close()
                election_thr = threading.Thread(target=election, args=(event,))
                election_thr.start()
                election_ongoing = True
        if index == 3 and recieved:
            recieved = False

def request_vote(candidate_term: int, participant: str, rank: list) -> bool:
    rank_str = ""
    for i in rank:
        rank_str += str(i)
        rank_str += ","
    rank_str = rank_str[:-1]

    message = "$REQUEST VOTE$;" + str(candidate_term) + ";" + rank_str

    try:
        participant_IP, participant_port = participant.split(":")
        participant_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        participant_socket.connect((participant_IP, int(participant_port)))

        participant_socket.sendall(message.encode())

        peer_vote = participant_socket.recv(1024).decode()
        if peer_vote == "$yes$":
            participant_socket.close()
            return True
        else:
            participant_socket.close()
            return False

    except Exception as e:
        print(f"Could not send term to {participant}: {e}")
        return False

def election(event) -> None:
    global new_leader
    global election_ongoing
    global leader
    global candidate
    candidate.term += 1

    for participant in network_participants:
        if request_vote(candidate.term, participant, candidate.rank):
            candidate.votes += 1
        
        if candidate.votes > len(network_participants)//2:
            leader = True
            print("$Leadership Obtained$")
            new_leader = True
            leader_thr = threading.Thread(target=leader_thread, args=(event,network_participants,))
            leader_thr.start()
            election_ongoing = False

            reverse_proxy_host = "127.0.0.1"
            reverse_proxy_port = 9001

            # Connect to the reverse proxy server
            reverse_proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            reverse_proxy_socket.connect((reverse_proxy_host, reverse_proxy_port))

            # Force leader assignment request
            reverse_proxy_socket.sendall(f"$FORCE leader${HOST}:{PORT}".encode())
            break

def receive_thread(server_socket, event) -> None:
    global voted
    global network_participants
    global leader_socket

    network_participants = []
    connected_clients = {}
    client_sockets = []
    poller = select.poll()

    poller.register(server_socket, select.POLLIN)

    while not event.is_set():
        try:
            events = poller.poll(-1)

            for fd, ev in events:
                if fd == server_socket.fileno():
                    # New connection event
                    client_socket, client_address = server_socket.accept()
                    #print("New connection from:", client_address)

                    poller.register(client_socket, select.POLLIN)
                    connected_clients[client_socket.fileno()] = client_socket
                    client_sockets.append(client_socket)
                else:
                    client_socket = connected_clients[fd]
                    if ev & select.POLLIN:
                        data = client_socket.recv(4096).decode()
                        if data:
                            # For the leader to add all participant IPs
                            if "$FORCE leader$" in data and not leader:
                                data = data[14:]
                                leader_IP, leader_port = data.split(":")
                                leader_port = int(leader_port)
                                leader_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                leader_socket.connect((leader_IP, leader_port))
                            if "$addr$" in data and leader == True:
                                network_participants.append(data[6:])
                            # For the follower to receive heartbeats
                            elif "$HEARTBEAT$" in data and leader == False:
                                global voted
                                global recieved
                                voted = False
                                recieved = True
                                heartbeat = data[11:]
                                # Split the heartbeat into individual participants
                                heartbeat_participants = heartbeat.split(",")
                                # Filter out the current follower's IP and port
                                filtered_participants = [
                                    participant for participant in heartbeat_participants
                                    if participant != f"{HOST}:{PORT}"
                                ]
                                network_participants = filtered_participants
                            elif "$REQUEST VOTE$;" in  data:
                                global candidate
                                if not voted:
                                    data = data.split(";")
                                    other_term = int(data[1])
                                    other_rank = data[2].split(",")
                                    if candidate.term > other_term:
                                        client_socket.sendall("$no$".encode())
                                    elif candidate.term < other_term:
                                        client_socket.sendall("$yes$".encode())
                                    else:
                                        if candidate.compare_rank(other_rank):
                                            client_socket.sendall("$yes$".encode())
                                        else:
                                            client_socket.sendall("$no$".encode())
                                    voted = True
                                else:
                                    client_socket.sendall("$no$".encode())
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

def main() -> None:
    global new_leader

    global voted
    voted = False

    global candidate
    candidate = Candidate()

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
        new_leader = False
        reverse_proxy_socket.close()
        leader = True
        print("$Leadership Obtained$")
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)

        lead = threading.Thread(target=leader_thread, args=(event,[],))
        inp = threading.Thread(target=receive_thread, args=(server_socket, event,))
        out = threading.Thread(target=send_thread, args=(event,))

        lead.start()
        inp.start()
        out.start()

        lead.join()
        inp.join()
        out.join()

    else:
        new_leader = False
        reverse_proxy_socket.close()
        leader_IP, leader_port = response.split(":")

        leader_port = int(leader_port)
        global leader_socket
        leader_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        leader_socket.connect((leader_IP, leader_port))
        leader_socket.sendall(f"$addr${HOST}:{PORT}".encode())

        #leader_socket.close()

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)

        inp = threading.Thread(target=receive_thread, args=(server_socket, event,))
        out = threading.Thread(target=send_thread, args=(event,))
        timer = threading.Thread(target=timer_thread, args=(event,))

        inp.start()
        out.start()
        timer.start()

        inp.join()
        out.join()
        timer.join()

if __name__ == "__main__":
    main()
