# Peer To Peer Messaging Service

## Summary
This project aims to create group-chat-like networks in which each network participant communicates directly with other network participants without the use of a centralized server through which communications pass. The network employs a peer-to-peer architecture with a leader that stores network metadata (who is participating and what are their addresses). However, the leader is by no means a fixed entity. Should it fail, another peer will take its place through an election process following some of the principles of the Raft algorithm. This way, network data is appropriately managed and peers can leave the network gracefully while new participants can join.

## Components
 - Reverse Proxy Server -> The reverse proxy exists at a known address. Whenever a new peer wishes to join the network, it first connects to the reverse proxy as that is the only address it knows about (everything else in the network is variable). The reverse proxy then redirects the peer to the leader of the system. When a leader fails, the P2P network internally elects a new leader, and the reverse proxy is notified for future connections.
 - Peer -> A peer is simply a participant in the P2P network. It can be thought of as an individual's device in a group chat. Peers have sending and receiving threads that are interconnected with the rest of the peers in the network.
 - RSA Public Key Manager -> A trusted authority for public RSA key storage and retrieval. Allows for authentication during the key exchange process.

## Election
The leader of the network is tasked with sending out heartbeat messages at regular intervals. If a follower peer does not receive a heartbeat message for a certain duration of time, it will assume that the leader is dead and initiate an election. During an election, each candidate will request votes from other participants in the network. Upon receiving a request for a vote, a peer will vote "yes" by comparing two objects: term and rank. The term is the current election index. Peers will first compare this number: if the requesting peer's term is greater then the peer will vote "yes". If it is smaller, the peer will vote "no". If it is the same, the comparison moves to the rank. The rank is an array of randomly generated integers. Iterating through the array sequentially, if there is a number in the requesting peer's rank that is greater than the respective index in the voting peer's rank, the voting peer will vote "yes". It will also vote yes if – in the small chance – both the rank and term are the same. It will vote no otherwise. Finally, when a candidate receives the majority vote, it will become the new leader, notify the reverse proxy to redirect participants to itself, and begin sending heartbeat messages to all network participants.

## Instructions

Generate the public and private RSA keys for the RSA Key Manager (to ensure authenticity during communication) on the machine running the RSA Key Manager.
```
python3 generate_manager_keys.py
```
This will create both a private and public key file. Copy the public key file to all the systems that will join the network.

Start the reverse proxy server. Note that it will bind to the address specified in "config.yml".
```
python3 reverse_proxy.py
```
Start the RSA Key Manager:
```
python3 rsa_key_manager.py
```
Start the individual peers.
```
python3 peer.py
```
The peer will prompt for a username. 
After this, it will prompt the user to specify if the IP should be derived on its own. 
Note that some Linux systems will simply use the localhost IP "127.0.0.1" which is why a manual option exists. 
The peer will then prompt for a port to bind to. 
Wait until the key manager states "Ready" before starting other peers.
Finally, connect multiple peers and messages will flow between them. 

To end a peer, simply type "$exit".
