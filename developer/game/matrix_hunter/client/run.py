import sys, socket, threading, os, time
from protocol import send_json, recv_json

pid = None
game_size = [20, 10]
state = None
running = True

def net(sock):
    global pid, state, game_size, running
    try:
        while running:
            msg = recv_json(sock)
            if not msg: 
                break
            
            if "pid" in msg:
                pid = msg["pid"]
                game_size = msg["size"]
            else:
                state = msg
                render()
    except Exception as e:
        print(f"\n[系統] 連線中斷: {e}")
    finally:
        running = False

def render():
    if state is None or pid is None:
        return
    
    w, h = game_size
    grid = [["  " for _ in range(w)] for _ in range(h)]
    
    # 1. 繪製子彈
    for b_pos in state.get('bullets', []):
        bx, by = b_pos
        if 0 <= bx < w and 0 <= by < h:
            grid[by][bx] = "‧"
        
    # 2. 繪製玩家
    for p_id_str, p_info in state.get('players', {}).items():
        p_id = int(p_id_str)
        px, py = p_info['pos']
        
        char = "🤖" if p_id == pid else "👾"
        if p_info['hp'] <= 0: char = "💀"
        
        if 0 <= px < w and 0 <= py < h:
            grid[py][px] = char

    # 使用 ANSI 轉義碼將游標移回左上角 (比 clear 更快且不閃爍)
    # \033[H 是移到左上角, \033[J 是清除游標以下內容
    print("\033[H", end="")
    print(f"=== 矩陣獵人 (玩家 ID: {pid}) ===")
    print("+" + "--" * w + "+")
    for row in grid:
        print("|" + "".join(row) + "|")
    print("+" + "--" * w + "+")
    
    my_info = state['players'].get(str(pid))
    if my_info:
        hp = my_info['hp']
        heart_count = max(0, hp) // 20
        print(f" HP: {'❤️ ' * heart_count}{'🖤' * (5-heart_count)} ({hp}%)      ")
    else:
        print(" 你已陣亡！按 Q 退出遊戲          ")
    
    print(" [WASD]移動 [F]射擊 [Q]退出 (按完請按 Enter) ")

    if state.get("game_over"):
        print("\n" + "="*30)
        print("       戰鬥結束！")
        print("   3秒後自動返回大廳...")
        print("="*30)
        time.sleep(3)
        # 關鍵：結束行程，這會讓父程序 player_client 繼續執行
        os._exit(0)

def main(ip, port):
    global running
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((ip, int(port)))
    except Exception as e:
        print(f"[錯誤] 無法連線至伺服器: {e}")
        return

    # 先清空一次畫面
    os.system('cls' if os.name == 'nt' else 'clear')
    print("正在初始化遊戲數據...")

    t = threading.Thread(target=net, args=(sock,), daemon=True)
    t.start()

    while running:
        try:
            # 使用 input 接收指令
            cmd = input().strip().lower()
            if cmd == 'q': 
                running = False
                break
            if cmd in ['w', 'a', 's', 'd', 'f']:
                send_json(sock, {"cmd": cmd})
        except EOFError:
            break

    sock.close()
    print("遊戲結束，感謝遊玩！")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python run.py <ip> <port>")
    else:
        main(sys.argv[1], sys.argv[2])