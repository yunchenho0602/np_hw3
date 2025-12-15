# protocol.py
import struct
import socket
import json

MAX_LEN = 65536


def send_frame(sock: socket.socket, data: bytes) -> None:
    length = len(data)
    if length <= 0 or length > MAX_LEN:
        raise ValueError(f"invalid frame length: {length}")
    header = struct.pack('!I', length)
    tosend = header + data
    totalsent = 0
    while totalsent < len(tosend):
        sent = sock.send(tosend[totalsent:])
        if sent == 0:
            raise ConnectionError("socket connection broken")
        totalsent += sent


def recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("socket connection broken while receiving")
        buf.extend(chunk)
    return bytes(buf)


def recv_frame(sock: socket.socket) -> bytes:
    hdr = recv_exact(sock, 4)
    (length,) = struct.unpack('!I', hdr)
    if length <= 0 or length > MAX_LEN:
        raise ValueError(f"invalid incoming frame length: {length}")
    body = recv_exact(sock, length)
    return body


def send_json(sock: socket.socket, obj) -> None:
    send_frame(sock, json.dumps(obj).encode('utf-8'))


def recv_json(sock: socket.socket):
    raw = recv_frame(sock)
    return json.loads(raw.decode('utf-8'))