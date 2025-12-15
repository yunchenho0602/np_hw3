import sys
import socket
import threading
import os
from protocol import send_json, recv_json

last_msg_hash = None  # 用來記錄上次顯示的內容快照

def clear_screen():
    # 根據作業系統執行清空指令
    os.system('cls' if os.name == 'nt' else 'clear')

def render_ui(msg, pid):
    global last_msg_hash
    
    # 提取關鍵資訊來判斷是否需要刷新
    # 這裡我們將目前的狀態轉為字串做比較
    current_hash = str(msg.get("players")) + str(msg.get("result")) + str(msg.get("player_count"))
    
    if current_hash == last_msg_hash:
        return # 內容沒變，不刷新
    
    last_msg_hash = current_hash
    
    clear_screen()
    print("========================================")
    print(f"      剪刀石頭布 🎮 (你是玩家 {pid})")
    print("========================================")
    print(f" 目前人數: {msg.get('player_count')}/2")
    print("----------------------------------------")
    
    # 顯示玩家出拳狀態
    players_data = msg.get("players", {})
    for p_id, choice in players_data.items():
        # 如果是自己，顯示出拳；如果是對手，且遊戲沒結束，顯示隱藏
        display_choice = "思考中..."
        if choice:
            # 只有當結果公告中包含「獲勝」或「平手」時才顯示對方的拳，增加神祕感
            if "結果" in msg.get("result", "") or str(p_id) == str(pid):
                display_choice = choice.upper()
            else:
                display_choice = "已出拳 🔒"
        
        name_tag = f"玩家 {p_id}" + (" (你)" if str(p_id) == str(pid) else "")
        print(f" {name_tag.ljust(15)} : {display_choice}")
    
    print("----------------------------------------")
    print(f" 狀態公告: {msg.get('result')}")
    print("========================================")
    print(" [輸入指令] rock / paper / scissors (或 q 退出)")
    print("> ", end="", flush=True)

def net(sock):
    global pid
    try:
        while True:
            msg = recv_json(sock)
            if not msg: break
            
            if "pid" in msg:
                pid = msg["pid"]
            else:
                render_ui(msg, pid)
    except:
        pass

def main(ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((ip, int(port)))
    except Exception as e:
        print(f"[錯誤] 無法連線至伺服器: {e}")
        return

    # 啟動接收執行緒 (Daemon)
    threading.Thread(target=net, args=(sock,), daemon=True).start()

    while True:
        try:
            cmd = input().strip().lower()
            if cmd in ["rock", "paper", "scissors"]:
                send_json(sock, {"choice": cmd})
            elif cmd == "q":
                break
            else:
                print("無效指令，請輸入 rock, paper 或 scissors (或輸入 q 退出)")
        except EOFError:
            break

    sock.close()

if __name__=="__main__":
    main(sys.argv[1],sys.argv[2])
