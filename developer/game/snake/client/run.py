import sys, socket, threading, os, time, json, select
from protocol import send_json, recv_json

# 遊戲狀態
state = None
pid = None
game_size = [20, 15]
running = True

# --- Linux 專用非阻塞按鍵讀取 ---
import termios, tty
def get_key():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        # 使用 select 檢查是否有輸入，不阻塞 render
        rlist, _, _ = select.select([sys.stdin], [], [], 0.05)
        if rlist:
            ch = sys.stdin.read(1)
            if ch == '\x1b': # 處理方向鍵
                ch += sys.stdin.read(2)
                return {'\x1b[A': 'up', '\x1b[B': 'down', '\x1b[C': 'right', '\x1b[D': 'left'}.get(ch)
            return {'w': 'up', 's': 'down', 'a': 'left', 'd': 'right', 'q': 'quit'}.get(ch.lower())
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return None

def render():
    if state is None: return
    W, H = game_size
    # Linux 終端機對 Emoji 寬度較敏感，初始化使用雙空格
    grid = [["  " for _ in range(W)] for _ in range(H)]
    
    if 'food' in state:
        fx, fy = state['food']
        if 0 <= fx < W and 0 <= fy < H: grid[fy][fx] = "🍎"
    
    snakes_data = state.get('snakes', {})
    for s_pid_str, body in snakes_data.items():
        is_self = (int(s_pid_str) == pid)
        h_char, b_char = ("🐲", "🔵") if is_self else ("👹", "🔴")
        for i, (bx, by) in enumerate(body):
            if 0 <= bx < W and 0 <= by < H:
                grid[by][bx] = h_char if i == 0 else b_char

    # --- 強力刷新與排版修正 ---
    out = []
    # 使用 \033[H 將游標移回左上角，不使用全清，防止閃爍
    out.append("\033[H")
    out.append(f"=== Linux 終端機多人對抗 (ID:{pid}) ===")
    out.append("┏" + "━━" * W + "┓")
    for row in grid:
        out.append("┃" + "".join(row) + "┃")
    out.append("┗" + "━━" * W + "┛")
    
    if state.get('game_over'):
        out.append("\n [💥 碰撞！] 遊戲結束...")
    else:
        out.append(" [WASD/方向鍵] 移動 | [Q] 退出")

    sys.stdout.write("\n".join(out))
    sys.stdout.flush()

def main():
    global state, pid, running
    if len(sys.argv) < 3: return
    ip, port = sys.argv[1], int(sys.argv[2])
    
    s = socket.socket()
    try:
        s.connect((ip, port))
        s.setblocking(False) # 將 Socket 設為非阻塞
        
        # 進入遊戲前清空一次畫面
        sys.stdout.write("\033[2J")
        
        while running:
            # 1. 處理輸入
            key = get_key()
            if key == 'quit': break
            if key: send_json(s, {"cmd": key})
            
            # 2. 處理資料接收
            try:
                msg = recv_json(s)
                if msg:
                    if "pid" in msg:
                        pid, game_size[:] = msg["pid"], msg.get("size", [20,15])
                    else:
                        state = msg
                        render()
                        if msg.get("game_over"): break
            except:
                pass # 沒資料就繼續跑 render
            
            time.sleep(0.05) # 降低 CPU 負載
            render()

    finally:
        s.close()
        print("\033[?25h") # 恢復游標顯示

if __name__ == "__main__":
    main()