import socket
import select
import threading
import time
import copy
from candidate import Candidate

class Message_Process:
    def __init__(self, host, port, user_name, leader=False):
        self.host = host
        self.port = port
        self.user_name = user_name
        self.network_participants = []
        self.leader_socket = None
        self.participant_dict = {}
        self.election_ongoing = False
        self.candidate = Candidate()
        self.leader = leader
        self.new_leader = False
        self.voted = False
        self.received = False
        self.event = threading.Event()

    def leader_thread(self, net_part) -> None:
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
        self.network_participants = copy.deepcopy(net_part)
        self.participant_dict = {}

        # As long as the user does not type $exit
        while not self.event.is_set():
            time.sleep(1.5)
            if not broadcast_addr and self.new_leader:
                message = f"$FORCE leader${self.host}:{self.port}"
                for participant in self.network_participants:
                    sock = self.participant_dict.get(participant)
                    if sock == None:
                        participant_IP, participant_port = participant.split(":")
                        participant_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        try:
                            participant_socket.connect((participant_IP, int(participant_port)))
                        except:
                            print(f"Could not add new participant {participant_IP}:{participant_port}")
                            self.network_participants.remove(participant)  
                            continue
                        self.participant_dict[participant] = participant_socket
                        sock = self.participant_dict.get(participant)
                    try:
                        sock.sendall(message.encode())
                    except:
                        self.network_participants.remove(participant)
                        self.participant_dict[participant] = None
                broadcast_addr = True
            else:
                message = "$HEARTBEAT$"
                for participant in self.network_participants:
                    message += participant
                    message += ","
                message = message[:-1]

                for participant in self.network_participants:
                    sock = self.participant_dict.get(participant)
                    if sock == None:
                        participant_IP, participant_port = participant.split(":")
                        participant_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        try:
                            participant_socket.connect((participant_IP, int(participant_port)))
                        except:
                            print(f"Could not add new participant {participant_IP}:{participant_port}")
                            self.network_participants.remove(participant)  
                            continue
                        self.participant_dict[participant] = participant_socket
                        sock = self.participant_dict.get(participant)
                    try:
                        sock.sendall(message.encode())
                    except:
                        self.network_participants.remove(participant)
                        self.participant_dict[participant] = None

    def send_thread(self) -> None:
        while not self.event.is_set():
            message = "$msg$;"
            message += input("")
            message += ";"
            message += self.host
            message += ";"
            message += str(self.port)
            message += ";"
            message += self.user_name

            if "$msg$;$exit" in message:
                self.event.set()
                break
            
            if not self.leader:
                try:
                    self.leader_socket.sendall(message.encode())
                except:
                    print("Could not send to leader")
                
            for participant in self.network_participants:
                sock = self.participant_dict.get(participant)
                if sock == None:
                    participant_IP, participant_port = participant.split(":")
                    participant_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    try:
                        participant_socket.connect((participant_IP, int(participant_port)))
                    except:
                        print(f"Could not add new participant {participant_IP}:{participant_port}")
                        self.network_participants.remove(participant)  
                        continue
                    self.participant_dict[participant] = participant_socket
                    sock = self.participant_dict.get(participant)
                try:
                    sock.sendall(message.encode())
                except:
                    self.network_participants.remove(participant)
                    self.participant_dict[participant] = None

    def timer_thread(self) -> None:
        self.election_ongoing = False
        self.received = False
        index = 0
        while not self.event.is_set() and not self.leader:
            if self.received:
                self.received = False
                index = 0
            time.sleep(1)
            index += 1
            if index > 3:
                if not self.election_ongoing and not self.leader and not self.received:
                    if len(self.network_participants)<2:
                        self.event.set()
                        print("Too Few Network Participants")
                        print("Exiting...")
                        break
                    self.leader_socket.close()
                    election_thr = threading.Thread(target=self.election, args=())
                    election_thr.start()
                    index = 0

    def request_vote(self, candidate_term, participant, rank) -> bool:
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
        
    def election(self) -> None:
        self.candidate.term += 1

        self.election_ongoing = True
        for participant in self.network_participants:
            if not self.election_ongoing:
                break
            
            if self.request_vote(self.candidate.term, participant, self.candidate.rank):
                print(f"{participant} voted in favor")
                self.candidate.votes += 1
            else:
                print(f"{participant} voted against")

            if self.candidate.votes > len(self.network_participants)//2:
                self.leader = True
                print("$Leadership Obtained$")
                self.new_leader = True
                leader_thr = threading.Thread(target=self.leader_thread, args=(copy.deepcopy(self.network_participants),))
                leader_thr.start()
                self.election_ongoing = False

                reverse_proxy_host = "127.0.0.1"
                reverse_proxy_port = 9001

                # Connect to the reverse proxy server
                reverse_proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                reverse_proxy_socket.connect((reverse_proxy_host, reverse_proxy_port))

                # Force leader assignment request
                reverse_proxy_socket.sendall(f"$FORCE leader${self.host}:{self.port}".encode())
                break

    def receive_thread(self, server_socket) -> None:
        self.network_participants = []
        connected_clients = {}
        client_sockets = []
        poller = select.poll()

        poller.register(server_socket, select.POLLIN)

        while not self.event.is_set():
            try:
                events = poller.poll(-1)

                for fd, ev in events:
                    if fd == server_socket.fileno():
                        client_socket, _ = server_socket.accept()

                        poller.register(client_socket, select.POLLIN)
                        connected_clients[client_socket.fileno()] = client_socket
                        client_sockets.append(client_socket)
                    else:
                        client_socket = connected_clients[fd]
                        if ev & select.POLLIN:
                            data = client_socket.recv(4096).decode()
                            if data:
                                if "$FORCE leader$" in data and not self.leader:
                                    self.election_ongoing = False
                                    self.voted = False
                                    try:
                                        self.leader_socket.close()
                                    except:
                                        pass
                                    data = data[14:]
                                    leader_IP, leader_port = data.split(":")
                                    leader_port = int(leader_port)
                                    self.leader_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                    self.leader_socket.connect((leader_IP, leader_port))
                                # For the leader to add all participant IPs
                                if "$addr$" in data and self.leader:
                                    self.network_participants.append(data[6:])
                                # For the follower to receive heartbeats
                                elif "$HEARTBEAT$" in data and self.leader == False:
                                    self.election_ongoing = False
                                    self.received = True
                                    heartbeat = data[11:]
                                    # Split the heartbeat into individual participants
                                    heartbeat_participants = heartbeat.split(",")
                                    # Filter out the current follower's IP and port
                                    filtered_participants = [
                                        participant for participant in heartbeat_participants
                                        if participant != f"{self.host}:{self.port}"
                                    ]
                                    self.network_participants = filtered_participants
                                elif "$REQUEST VOTE$;" in  data:
                                    if not self.voted:
                                        data = data.split(";")
                                        other_term = int(data[1])
                                        other_rank = data[2].split(",")
                                        if self.candidate.term > other_term:
                                            client_socket.sendall("$no$".encode())
                                        elif self.candidate.term < other_term:
                                            client_socket.sendall("$yes$".encode())
                                        else:
                                            if self.candidate.compare_rank(other_rank):
                                                client_socket.sendall("$yes$".encode())
                                            else:
                                                client_socket.sendall("$no$".encode())
                                        self.voted = True
                                    else:
                                        client_socket.sendall("$no$".encode())
                                elif "$msg$" in data:
                                    data = data.split(";")
                                    print(f"{data[2]}:{data[3]} ({data[4]}): {data[1]}")
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

    def start_leader(self):
        self.leader = True
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)

        lead = threading.Thread(target=self.leader_thread, args=([],))
        inp = threading.Thread(target=self.receive_thread, args=(server_socket,))
        out = threading.Thread(target=self.send_thread, args=())

        lead.start()
        inp.start()
        out.start()

        lead.join()
        inp.join()
        out.join()
    
    def start_follower(self, response):
        leader_IP, leader_port = response.split(":")

        leader_port = int(leader_port)
        self.leader_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.leader_socket.connect((leader_IP, leader_port))
        self.leader_socket.sendall(f"$addr${self.host}:{self.port}".encode())

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)

        inp = threading.Thread(target=self.receive_thread, args=(server_socket,))
        out = threading.Thread(target=self.send_thread, args=())
        timer = threading.Thread(target=self.timer_thread, args=())

        inp.start()
        out.start()
        timer.start()

        inp.join()
        out.join()
        timer.join()