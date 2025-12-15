import socket, threading, sys, time, random
from protocol import send_json, recv_json

# 遊戲設定
W, H = 20, 15
players = {}   # pid -> socket
snakes = {}    # pid -> [[x,y], [x,y]...]
dirs = {}      # pid -> [dx, dy]
food = [random.randint(0, W-1), random.randint(0, H-1)]
lock = threading.Lock()
game_over = False

def handle(conn, pid):
    global dirs
    try:
        while not game_over:
            msg = recv_json(conn)
            if not msg: break
            cmd = msg.get("cmd")
            with lock:
                # 支援 WASD 與方向鍵邏輯 (由客戶端轉換)
                if cmd == 'up' and dirs[pid] != [0, 1]: dirs[pid] = [0, -1]
                elif cmd == 'down' and dirs[pid] != [0, -1]: dirs[pid] = [0, 1]
                elif cmd == 'left' and dirs[pid] != [1, 0]: dirs[pid] = [-1, 0]
                elif cmd == 'right' and dirs[pid] != [-1, 0]: dirs[pid] = [1, 0]
    except: pass

def game_loop():
    global food, game_over
    while not game_over:
        time.sleep(0.4) # 調慢一點點，手感更好
        with lock:
            if len(snakes) < 2: continue # 等兩個人都進來才動
            
            dead_pids = []
            for pid in list(snakes.keys()):
                # 1. 計算新的頭部位置，並使用 % 運算子實現穿牆
                # (x + dx) % W 會讓 20 變成 0，讓 -1 變成 19
                new_x = (snakes[pid][0][0] + dirs[pid][0]) % W
                new_y = (snakes[pid][0][1] + dirs[pid][1]) % H
                head = [new_x, new_y]
                
                # 2. 修改碰撞檢查：現在不再檢查撞牆，只檢查「撞到自己或其他蛇的身體」
                # 注意：any() 檢查時要排除掉「這條蛇即將移動走的身軀末端」或是單純檢查新頭部是否在現有蛇群中
                collision = False
                for s_pid, s_body in snakes.items():
                    if head in s_body:
                        collision = True
                        break
                
                if collision:
                    dead_pids.append(pid)
                    continue

                # 3. 正常的移動邏輯
                snakes[pid].insert(0, head)
                if head == food:
                    # 吃到食物，重新生成食物位置
                    food = [random.randint(0, W-1), random.randint(0, H-1)]
                else:
                    # 沒吃到食物，移除尾巴
                    snakes[pid].pop()

            if dead_pids:
                game_over = True

            snapshot = {"snakes": snakes, "food": food, "game_over": game_over}
            for p_sock in players.values():
                try: send_json(p_sock, snapshot)
                except: pass
    
    time.sleep(3) # 讓玩家看一眼最後的畫面
    sys.exit(0)

def main(port):
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", int(port)))
    s.listen()
    threading.Thread(target=game_loop, daemon=True).start()
    
    global next_pid
    next_pid = 0
    while True:
        c, _ = s.accept()
        pid = next_pid
        next_pid += 1
        with lock:
            players[pid] = c
            snakes[pid] = [[0 if pid==0 else W-1, H//2]]
            dirs[pid] = [1, 0] if pid==0 else [-1, 0]
        send_json(c, {"pid": pid, "size": [W, H]})
        threading.Thread(target=handle, args=(c, pid), daemon=True).start()

if __name__ == "__main__":
    main(sys.argv[1])