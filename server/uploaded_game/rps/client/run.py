import sys
import socket
import threading
import os
from protocol import send_json, recv_json

last_msg_hash = None

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def render_ui(msg, pid):
    global last_msg_hash
    
    current_hash = str(msg.get("players")) + str(msg.get("result")) + str(msg.get("player_count"))
    
    if current_hash == last_msg_hash:
        return
    
    last_msg_hash = current_hash
    
    clear_screen()
    print("========================================")
    print(f"      剪刀石頭布 🎮 (你是玩家 {pid})")
    print("========================================")
    print(f" 目前人數: {msg.get('player_count')}/2")
    print("----------------------------------------")
    
    players_data = msg.get("players", {})
    for p_id, choice in players_data.items():
        display_choice = "思考中..."
        if choice:
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
