# 通用遊戲模板：run.py
import sys
import socket
import threading
import os

current = os.path.dirname(os.path.abspath(__file__))

while True:
    parent = os.path.dirname(current)
    if parent == current:
        break  # 找到 filesystem root 了
    if os.path.isdir(os.path.join(parent, "common")):
        sys.path.insert(0, parent)
        break
    current = parent

from common.protocol import send_json, recv_json

def game_loop(sock):
    """子執行緒，不停接收伺服器資料"""
    try:
        while True:
            msg = recv_json(sock)
            print("[伺服器訊息]", msg)
    except:
        print("[連線中斷]")
        sock.close()

def main():
    if len(sys.argv) < 4:
        print("Usage: python run.py <username> <server_ip> <server_port>")
        sys.exit(1)

    username = sys.argv[1]
    server_ip = sys.argv[2]
    server_port = int(sys.argv[3])

    print(f"[遊戲啟動] {username} connecting to {server_ip}:{server_port}")

    sock = socket.socket()
    sock.connect((server_ip, server_port))

    send_json(sock, {
        "cmd": "join",
        "username": username
    })

    threading.Thread(target=game_loop, args=(sock,), daemon=True).start()

    # 開發者可從這裡開始寫遊戲邏輯
    print("[系統] 請開始撰寫你的遊戲邏輯！")

    while True:
        text = input("你要送出的指令：")
        send_json(sock, {"cmd": "input", "value": text})

if __name__ == "__main__":
    main()
