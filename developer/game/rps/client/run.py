import sys
import socket
import threading
import os
from protocol import send_json, recv_json

pid = None
last_state = None

def net(sock):
    """監聽執行緒：不斷接收伺服器廣播的 snapshot"""
    global pid, last_state
    try:
        while True:
            msg = recv_json(sock)
            if "pid" in msg:
                pid = msg["pid"]
                print(f"\n[系統] 成功登入，你的編號是：玩家 {pid}")
            else:
                last_state = msg
                # 清除畫面 (選用，根據需求)
                # os.system('cls' if os.name == 'nt' else 'clear')
                print(f"\n--- 遊戲狀態 ---")
                print(f"目前人數: {msg.get('player_count')}")
                for p, choice in msg.get("players", {}).items():
                    c_display = choice if choice else "思考中..."
                    print(f"玩家 {p}: {c_display}")
                print(f"公告: {msg.get('result')}")
                print(f"----------------")
                print("請輸入 rock / paper / scissors: ", end="", flush=True)
    except Exception as e:
        print(f"\n[錯誤] 與伺服器斷開連線: {e}")

def main(user, ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((ip, int(port)))
    except Exception as e:
        print(f"[錯誤] 無法連線至伺服器: {e}")
        return

    # 啟動接收執行緒 (Daemon)
    threading.Thread(target=net, args=(sock,), daemon=True).start()

    print(f"歡迎 {user} 進入剪刀石頭布遊戲！")
    
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

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("使用方式: python run.py <user> <ip> <port>")
    else:
        # 注意：sys.argv[1] 是使用者名稱，argv[2] 是 IP，argv[3] 是 Port
        main(sys.argv[1], sys.argv[2], sys.argv[3])