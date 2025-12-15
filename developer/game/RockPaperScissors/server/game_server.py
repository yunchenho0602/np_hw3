import sys
import socket
import threading
from protocol import send_json, recv_json

players = {}   # conn -> choice
conns = []     # 玩家連線
lock = threading.Lock()

RULES = {
    "rock": "scissors",
    "scissors": "paper",
    "paper": "rock"
}

def judge(p1, p2):
    if p1 == p2:
        return "DRAW"
    if RULES[p1] == p2:
        return "P1"
    return "P2"
def handle_player(conn, pid):
    global players
    try:
        send_json(conn, {"type": "INFO", "message": f"你是玩家 {pid}，請輸入 rock / paper / scissors"})
        data = recv_json(conn)
        choice = data.get("choice")

        with lock:
            players[conn] = choice

            if len(players) == 2:
                c1, c2 = conns[0], conns[1]
                p1, p2 = players[c1], players[c2]
                result = judge(p1, p2)

                send_json(c1, {"type": "RESULT", "you": p1, "opponent": p2, "result": result})
                send_json(c2, {"type": "RESULT", "you": p2, "opponent": p1,
                               "result": result if result == "DRAW" else ("P2" if result == "P1" else "P1")})
    except Exception as e:
        print("[遊戲錯誤]", e)
    finally:
        conn.close()

def start_game_server(port, room_id):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('0.0.0.0', int(port)))
    s.listen(2)

    print(f"[RPS] Game Server on port {port}, room {room_id}")

    while len(conns) < 2:
        conn, addr = s.accept()
        print(f"[RPS] 玩家加入: {addr}")
        conns.append(conn)
        threading.Thread(target=handle_player, args=(conn, len(conns)), daemon=True).start()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
    start_game_server(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "None")
