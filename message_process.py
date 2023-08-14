from candidate import Candidate

import socket
import select
import threading
import time
import copy
import json
import yaml

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.asymmetric.padding import PSS, MGF1, OAEP, PKCS1v15
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

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
        self.curve = ec.SECP256R1()
        self.shared_key = None
        self.iv = b'\xf0<\x92)A7\xaf\\\xa6k\xd6\xfc\x99\x88\x03>' #initialization vector
        self.salt = b'<h\x1az\x94\x89\xec\x907\xe8\xc1\x8e\x03u\xe3\xa1'
        self.rsa_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
        self.rsa_public_key = self.rsa_private_key.public_key()
        self.private_key = ec.generate_private_key(self.curve, default_backend())
        self.public_key = self.private_key.public_key()
        self.key_dict = {}
        self.thread_map = {}
        self.leader_need_to_reconnect = False
        self.excheanged_with_leader = False
        self.leader_key = None
        self.manager_public_key = None
        self.manager_socket = None

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

            # This makes sure that every new leader broadcasts its adress to the followers
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
            
            # This is just the regular hearbeat with information about network participants
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
        '''
        The send thread defines how messages are sent from one peer to another. 
        The sending functionality is kept separate from the receiving functionality.
        '''
        # Each message contains information about who sent it and the respective username/receiving adress
        while not self.event.is_set():
            message = "$msg$;"
            message += input("")
            message += ";"
            message += self.host
            message += ";"
            message += str(self.port)
            message += ";"
            message += self.user_name

            # If the user types $exit, the peer shuts down
            if "$msg$;$exit" in message:
                self.event.set()
                break

            # Messages are sent to the leader separately
            if not self.leader:
                try:
                    if not self.excheanged_with_leader:
                        print("Connecting...")
                        leader_ip, leader_port = self.leader_socket.getpeername()
                        leader_addr = leader_ip+":"+str(leader_port)
                        self.send_encryption_details(self.leader_socket, True)
                        self.queue_send(self.leader_socket,leader_addr,message)
                        self.excheanged_with_leader = True
                    else:
                        encryptor = Cipher(algorithms.AES(self.key_dict.get(leader_addr)), modes.CFB(self.iv), backend=default_backend()).encryptor()
                        ciphertext = encryptor.update(message.encode()) + encryptor.finalize()
                        self.leader_socket.sendall(ciphertext)
                except:
                    print("Could not send to leader")
            
            # New leaders often need new shared keys so this is necessary
            if self.leader_need_to_reconnect:
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
                    print("Connecting...")
                    self.send_encryption_details(sock, True)
                    self.queue_send(sock,participant,message)
                self.leader_need_to_reconnect = False
                continue

            # Sending messages to all the other peers
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
                    print("Connecting...")
                    self.send_encryption_details(sock, True)
                    self.queue_send(sock,participant,message)
                    continue
                
                # key_dict tells us if we've already established a shared key with the peer
                # if we haven't, we start the process
                if self.key_dict.get(participant) == None:
                    print("Connecting...")
                    self.send_encryption_details(sock, True)
                    self.queue_send(sock,participant,message)
                    continue

                try:
                    encryptor = Cipher(algorithms.AES(self.key_dict.get(participant)), modes.CFB(self.iv), backend=default_backend()).encryptor()
                    ciphertext = encryptor.update(message.encode()) + encryptor.finalize()
                    sock.sendall(ciphertext)

                except:
                    self.network_participants.remove(participant)
                    self.participant_dict[participant] = None

    def queue_send(self, sockfd, participant, msg):
        '''
        When a message is sent to a new peer, there will be a delay between sending and the keys to be created. 
        This method will wat until the key is created to send the message.
        '''
        while self.key_dict.get(participant) == None:
            pass
        encryptor = Cipher(algorithms.AES(self.key_dict.get(participant)), modes.CFB(self.iv), backend=default_backend()).encryptor()
        ciphertext = encryptor.update(msg.encode()) + encryptor.finalize()
        sockfd.sendall(ciphertext)

    def send_encryption_details(self, sockfd: socket.socket, initiator: bool, misc = ""):
        signature = self.rsa_private_key.sign(self.public_key.public_bytes(encoding=serialization.Encoding.PEM,format=serialization.PublicFormat.SubjectPublicKeyInfo), PSS(mgf=MGF1(hashes.SHA256()), salt_length=PSS.MAX_LENGTH), hashes.SHA256())
        if initiator:
            data_dict = {
                "rsa_public_key": self.rsa_public_key.public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo).decode(),
                "ecdh_public_key": self.public_key.public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo).decode(),
                "initiator": "true",
                "identity": f"{self.host}:{self.port}",
                "signature": signature.hex(),
                "misc": "None"
            }
            json_bytes = json.dumps(data_dict).encode()
        else:
            data_dict = {
                "rsa_public_key": self.rsa_public_key.public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo).decode(),
                "ecdh_public_key": self.public_key.public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo).decode(),
                "initiator": "false",
                "identity": f"{self.host}:{self.port}",
                "signature": signature.hex(),
                "misc": misc
            }
            json_bytes = json.dumps(data_dict).encode()
        sockfd.sendall(json_bytes)
    
    def timer_thread(self) -> None:
        '''
        The timer thread is a crucial part of the re-election logic.
        It ensures that after a ceertain amount of time of not receiving a heartbeat from the leader,
        the follower will assume that the leader is dead and start an election.
        '''
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
                    # Check if there are enough participants for a majority to even happen
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
        '''
        This function outlies the logic of requsting a vote from another peer
        '''
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
        '''
        The election thread orchestrates the enetire election process and decides if the candidate becomes a leader
        '''
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

                # Update the reverse proxy on who is the leader so that new joining participants know where to connect
                reverse_proxy_socket.sendall(f"$FORCE leader${self.host}:{self.port}".encode())
                self.leader_need_to_reconnect = True
                break

    def receive_thread(self, server_socket) -> None:
        '''
        The receive thread receives most communications adressed to the peer.
        It employs polling to efficiently manage the large number of connections.
        '''
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
                            data = client_socket.recv(4096)
                            if data:
                                if data[:46] == b'{"rsa_public_key": "-----BEGIN PUBLIC KEY-----':
                                    temp_ip, temp_port = client_socket.getpeername()
                                    temp_addr = temp_ip+":"+str(temp_port)

                                    decoded_dict = json.loads(data.decode())
                                    
                                    key = decoded_dict["ecdh_public_key"].encode()
                                    sig = bytes.fromhex(decoded_dict["signature"])
                                    initiator = True if decoded_dict["initiator"] == "true" else False
                                    identity = decoded_dict["identity"]
                                    
                                    # Now obtain rsa public key from manager to verify signature
                                    self.manager_socket.sendall(f"$req{identity}".encode())
                                    key_pem = self.manager_socket.recv(1024)
                                    peer_rsa_public_key = serialization.load_pem_public_key(key_pem, default_backend())

                                    try:
                                        peer_rsa_public_key.verify(sig, key, PSS(mgf=MGF1(hashes.SHA256()), salt_length=PSS.MAX_LENGTH), hashes.SHA256())
                                    except:
                                        print("Unable to verify peer identity; aborting connection.")
                                        continue
                                    
                                    # We have passed RSA authentication
                                    peer_public_key = serialization.load_pem_public_key(key, default_backend())
                                    shared_key = self.private_key.exchange(ec.ECDH(), peer_public_key)
                                    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), iterations=100000, salt=self.salt, backend=default_backend(), length=32)
                                    aes_key = kdf.derive(shared_key)
                                    
                                    # Map the sending thread to the receiving thread
                                    self.thread_map[temp_addr] = identity

                                    # Now we can add the identity to our key_dict for future encrypted communication
                                    self.key_dict[identity] = aes_key

                                    if initiator:
                                        to_conn_ip, to_conn_port = identity.split(":")
                                        to_respond = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                        to_respond.connect((to_conn_ip,int(to_conn_port)))
                                        self.send_encryption_details(to_respond, False)

                                        # Add it to the partitipants dict to use for subsequent comms
                                        self.participant_dict[identity] = to_respond
                                    continue

                                try:
                                    decoded_data = data.decode()
                                    if "$FORCE leader$" in decoded_data and not self.leader:
                                        self.election_ongoing = False
                                        self.voted = False
                                        self.excheanged_with_leader = False
                                        try:
                                            self.leader_socket.close()
                                        except:
                                            pass
                                        decoded_data = decoded_data[14:]
                                        leader_IP, leader_port = decoded_data.split(":")
                                        leader_port = int(leader_port)
                                        self.leader_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                        self.leader_socket.connect((leader_IP, leader_port))
                                    # For the leader to add all participant IPs
                                    if "$addr$" in decoded_data and self.leader:
                                        self.network_participants.append(decoded_data[6:])

                                    # For the follower to receive heartbeats
                                    elif "$HEARTBEAT$" in decoded_data and self.leader == False:
                                        self.election_ongoing = False
                                        self.received = True
                                        heartbeat = decoded_data[11:]
                                        # Split the heartbeat into individual participants
                                        heartbeat_participants = heartbeat.split(",")
                                        # Filter out the current follower's IP and port
                                        filtered_participants = [
                                            participant for participant in heartbeat_participants
                                            if participant != f"{self.host}:{self.port}"
                                        ]
                                        self.network_participants = filtered_participants

                                    # This block outlines the logic if the peer must vote
                                    elif "$REQUEST VOTE$;" in  decoded_data:
                                        if not self.voted:
                                            decoded_data = decoded_data.split(";")
                                            other_term = int(decoded_data[1])
                                            other_rank = decoded_data[2].split(",")
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
                                    elif "$msg$" in decoded_data:
                                        decoded_data = decoded_data.split(";")
                                        print(f"{decoded_data[2]}:{decoded_data[3]} ({decoded_data[4]}): {decoded_data[1]}")
                                except:
                                    # The keys are assgned to the receiving threads so we want to get that adress from the sending thread adress we have
                                    temp_ip,temp_port = client_socket.getpeername()
                                    temp_addr = temp_ip+":"+str(temp_port)
                                    key = self.key_dict.get(self.thread_map.get(temp_addr))
                            
                                    decryptor = Cipher(algorithms.AES(key), modes.CFB(self.iv), backend=default_backend()).decryptor()
                                    decrypted_text = decryptor.update(data) + decryptor.finalize()
                                    msg = decrypted_text.decode()
                                    msg = msg.split(";")
                                    print(f"{msg[2]}:{msg[3]} ({msg[4]}): {msg[1]}")
                                    continue
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
        '''
        This function is called when the first leader in the network is to be started.
        It serves no other purpose than to kickstart the network.
        '''
        with open("config.yml", "r") as f:
            config = yaml.safe_load(f)
        manager_host = config["key_manager_host"]
        manager_port = config["key_manager_port"]

        self.manager_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.manager_socket.connect((manager_host,manager_port))
        self.get_manager_public_key()
        self.send_manager_key()

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
        '''
        This function is called when the follower first joins the network.
        It serves no other purpose than to kickstart the follower.
        '''
        with open("config.yml", "r") as f:
            config = yaml.safe_load(f)
            manager_host = config["key_manager_host"]
            manager_port = config["key_manager_port"]

        self.manager_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.manager_socket.connect((manager_host,manager_port))
        self.get_manager_public_key()
        self.send_manager_key()
        
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
    
    def get_manager_public_key(self):
        with open("manager_public_key.pem", "rb") as f:
            rsa_public_key_pem = f.read()
            self.manager_public_key = serialization.load_pem_public_key(rsa_public_key_pem, backend=default_backend())
    
    def send_manager_key(self):
        rsa_public_key_pem = self.rsa_public_key.public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo)
        addr = self.host+":"+str(self.port)

        data = {
            "public_key": rsa_public_key_pem.decode('utf-8'),
            "address": addr
        }
        json_data = json.dumps(data).encode('utf-8')

        encrypted_key = self.manager_public_key.encrypt(json_data, OAEP(mgf=MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
        self.manager_socket.sendall(encrypted_key)