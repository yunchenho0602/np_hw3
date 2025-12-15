import socket, threading, sys, time
from protocol import send_json, recv_json

# 遊戲設定
WIDTH, HEIGHT = 20, 10
players = {}   # pid -> socket
states = {}    # pid -> {pos: [x,y], hp: 100, dir: [dx,dy]}
bullets = []   # list of {pos: [x,y], dir: [dx,dy], owner: pid}
lock = threading.Lock()
next_pid = 0

def handle(conn, pid):
    global states
    try:
        while True:
            msg = recv_json(conn)
            if not msg: break
            
            cmd = msg.get("cmd")
            with lock:
                if pid not in states or states[pid]['hp'] <= 0: continue
                
                # 處理移動 (W/A/S/D)
                if cmd == 'w': states[pid]['pos'][1] = max(0, states[pid]['pos'][1]-1); states[pid]['dir']=[0,-1]
                elif cmd == 's': states[pid]['pos'][1] = min(HEIGHT-1, states[pid]['pos'][1]+1); states[pid]['dir']=[0,1]
                elif cmd == 'a': states[pid]['pos'][0] = max(0, states[pid]['pos'][0]-1); states[pid]['dir']=[-1,0]
                elif cmd == 'd': states[pid]['pos'][0] = min(WIDTH-1, states[pid]['pos'][0]+1); states[pid]['dir']=[1,0]
                
                # 處理射擊 (F)
                elif cmd == 'f':
                    bullets.append({
                        "pos": list(states[pid]['pos']),
                        "dir": list(states[pid]['dir']),
                        "owner": pid
                    })
    except: pass
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
            
            # 檢查是否有人 HP <= 0
            game_over = any(s['hp'] <= 0 for s in states.values())
            
            snapshot = {
                "players": {pid: {"pos": s["pos"], "hp": s["hp"]} for pid, s in states.items()},
                "bullets": [b['pos'] for b in bullets],
                "game_over": game_over # 告訴客戶端遊戲是否結束
            }
            
            for p in players.values():
                try: send_json(p, snapshot)
                except: pass
            
            # 如果結束了，伺服器可以在幾秒後停止
            if game_over:
                time.sleep(5)
                break

def main(port):
    global next_pid
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", int(port)))
    s.listen()
    threading.Thread(target=game_loop, daemon=True).start()

    while True:
        c, _ = s.accept()
        pid = next_pid
        next_pid += 1
        with lock:
            players[pid] = c
            states[pid] = {"pos": [0, pid % HEIGHT], "hp": 100, "dir": [1, 0]}
        send_json(c, {"pid": pid, "size": [WIDTH, HEIGHT]})
        threading.Thread(target=handle, args=(c, pid), daemon=True).start()

if __name__ == "__main__":
    main(sys.argv[1])