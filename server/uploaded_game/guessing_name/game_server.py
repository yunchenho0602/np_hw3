# game_server.py
import sys
import socket
import threading
import random
from protocol import send_json, recv_json

players = []          # [(conn, username)]
answer = random.randint(1, 100)
turn = 0
lock = threading.Lock()

def handle_player(conn, addr):
    global turn
    data = recv_json(conn)
    username = data["username"]

    with lock:
        players.append((conn, username))
        pid = len(players) - 1

    send_json(conn, {
        "type": "info",
        "msg": f"你是玩家 {pid}，等待另一位玩家"
    })

    while True:
        with lock:
            if len(players) < 2 or pid != turn:
                continue

        send_json(conn, {"type": "your_turn"})
        guess = recv_json(conn)["guess"]

        with lock:
            if guess == answer:
                for c, _ in players:
                    send_json(c, {
                        "type": "end",
                        "winner": username,
                        "answer": answer
                    })
                break
            elif guess < answer:
                send_json(conn, {"type": "hint", "msg": "太小"})
            else:
                send_json(conn, {"type": "hint", "msg": "太大"})

            turn = 1 - turn

def start_game_server(port, room_id):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("0.0.0.0", int(port)))
    s.listen(2)

    print(f"[GameServer] 雙人猜數字遊戲啟動 Port={port}, Room={room_id}")

    while len(players) < 2:
        conn, addr = s.accept()
        threading.Thread(
            target=handle_player,
            args=(conn, addr),
            daemon=True
        ).start()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
    start_game_server(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "None")
