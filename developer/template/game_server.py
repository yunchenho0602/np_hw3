# 通用遊戲模板：game_server.py
import socket
import threading
import sys
import os

current = os.path.dirname(os.path.abspath(__file__))

while True:
    parent = os.path.dirname(current)
    if parent == current:
        break  # 找到 filesystem root 了
    if os.path.isdir(os.path.join(parent, "common")):
        sys.path.insert(0, parent)
        break
    current = parent

from common.protocol import send_json, recv_json
players = []

def handle_player(conn, addr):
    print(f"[玩家連線] {addr}")
    players.append(conn)

    try:
        while True:
            data = recv_json(conn)
            print(f"[收到] {addr}: {data}")

            # 廣播給所有玩家
            for p in players:
                if p != conn:
                    send_json(p, {"from": str(addr), "data": data})
    except:
        print(f"[玩家離線] {addr}")
        players.remove(conn)
        conn.close()

def start_game_server(port, room_id):
    print(f"[Game Server] Start at port={port}, room={room_id}")

    s = socket.socket()
    s.bind(("0.0.0.0", int(port)))
    s.listen(8)

    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_player, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    port = sys.argv[1]
    room = sys.argv[2] if len(sys.argv) > 2 else "None"
    start_game_server(port, room)
