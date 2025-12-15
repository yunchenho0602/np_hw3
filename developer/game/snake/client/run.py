import sys, socket, threading, os, time
from protocol import send_json, recv_json

# --- 跨平台讀取按鍵邏輯 ---
if os.name == 'nt':
    import msvcrt
    def get_key():
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            if ch in [b'\xe0', b'\x00']: # 方向鍵特徵碼
                ch = msvcrt.getch()
                return {b'H': 'up', b'P': 'down', b'K': 'left', b'M': 'right'}.get(ch)
            return {b'w': 'up', b's': 'down', b'a': 'left', b'd': 'right', b'q': 'quit'}.get(ch.lower())
        return None
else:
    import termios, tty
    def get_key():
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
            if ch == '\x1b': # Linux 方向鍵處理
                ch += sys.stdin.read(2)
                return {'\x1b[A': 'up', '\x1b[B': 'down', '\x1b[C': 'right', '\x1b[D': 'left'}.get(ch)
            return {'w': 'up', 's': 'down', 'a': 'left', 'd': 'right', 'q': 'quit'}.get(ch.lower())
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

# --- 遊戲主邏輯 ---
pid, state, running = None, None, True
game_size = [20, 15]

def net(sock):
    global pid, state, running
    try:
        while running:
            msg = recv_json(sock)
            if not msg: break
            if "pid" in msg:
                pid, game_size[:] = msg["pid"], msg["size"]
            else:
                state = msg
                render()
                if msg.get("game_over"):
                    time.sleep(2)
                    running = False
                    break
    except: running = False

def render():
    if not state: return
    W, H = game_size
    grid = [["  " for _ in range(W)] for _ in range(H)]
    fx, fy = state['food']
    grid[fy][fx] = "🍎"
    
    for s_pid_str, body in state['snakes'].items():
        char = "🔵" if int(s_pid_str) == pid else "🔴"
        for i, (bx, by) in enumerate(body):
            if 0 <= bx < W and 0 <= by < H: grid[by][bx] = char if i > 0 else "🐲"

    print("\033[H", end="") # 游標移回頂部，達成原地刷新
    print(f"=== 貪吃蛇大對抗 (玩家:{pid}) ===")
    print("┏" + "━━"*W + "┓")
    for row in grid: print("┃" + "".join(row) + "┃")
    print("┗" + "━━"*W + "┛")
    if state['game_over']: print("\n [💥 碰撞！] 遊戲結束，正自動返回大廳...")
    else: print(" [操作] 直接按方向鍵 或 WASD 移動 | Q 退出 ")

def main(ip, port):
    sock = socket.socket()
    sock.connect((ip, int(port)))
    os.system('cls' if os.name == 'nt' else 'clear')
    threading.Thread(target=net, args=(sock,), daemon=True).start()

    while running:
        key = get_key()
        if key == 'quit': break
        if key: send_json(sock, {"cmd": key})
        time.sleep(0.05) # 降低 CPU 負擔
    sock.close()

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])