import socket
import threading
import sys
import time
from protocol import send_json, recv_json

players = {}   
states = {}    
lock = threading.Lock()
next_pid = 0

def judge(choices):
    if len(choices) < 2:
        return "等待對手中..."
    
    p0 = choices.get(0)
    p1 = choices.get(1)
    
    if not p0 or not p1:
        return "等待雙方出拳..."
        
    if p0 == p1:
        return "結果：平手！"
    
    wins = {"rock": "scissors", "scissors": "paper", "paper": "rock"}
    if wins[p0] == p1:
        return "結果：玩家 0 獲勝！"
    else:
        return "結果：玩家 1 獲勝！"

def handle(conn, pid):
    global states
    try:
        while True:
            msg = recv_json(conn)
            if not msg:
                break
            choice = msg.get("choice")
            if choice in ["rock", "paper", "scissors"]:
                with lock:
                    states[pid] = choice
    except Exception as e:
        print(f"[異常] 玩家 {pid} 斷開連線: {e}")
    finally:
        with lock:
            if pid in players: del players[pid]
            if pid in states: del states[pid]
        conn.close()

def game_loop():
    while True:
        time.sleep(0.3)
        with lock:
            if not players: continue
            
            current_choices = {}
            for p_id in players.keys():
                current_choices[p_id] = states.get(p_id)

            result_msg = judge(current_choices)
            snapshot = {
                "players": current_choices,
                "result": result_msg,
                "player_count": len(players)
            }
            
            for pid, p_sock in list(players.items()):
                try:
                    send_json(p_sock, snapshot)
                except:
                    pass

def main(port):
    global next_pid
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", int(port)))
    s.listen(2)

    print(f"[RPS 伺服器] 啟動於 Port {port}，等待玩家...")
    
    threading.Thread(target=game_loop, daemon=True).start()

    while True:
        try:
            c, addr = s.accept()
            with lock:
                pid = next_pid
                next_pid += 1
                players[pid] = c
                states[pid] = None 
                
                print(f"[連線] 玩家 {pid} 已加入 ({addr})")
                send_json(c, {"pid": pid})
                
            threading.Thread(target=handle, args=(c, pid), daemon=True).start()
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方式: python game_server.py <port>")
    else:
        main(sys.argv[1])