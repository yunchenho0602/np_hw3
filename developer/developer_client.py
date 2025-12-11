import socket
import sys
import os
import json

# --- 路徑設定 ---
# 讓 client 能找到上一層的 common
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# --- Import ---
from common.protocol import send_json, recv_json
from common.constant import SERVER_PORT, SERVER_IP

class DevClient:
    def __init__(self):
        self.sock = None
        self.is_connected = False
        self.user_data = None  # 登入成功後存使用者資料

    def connect(self):
        """連線到 Server"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((SERVER_IP, SERVER_PORT))
            self.is_connected = True
            print(f"[連線] 成功連線到 {SERVER_IP}:{SERVER_PORT}")
        except Exception as e:
            print(f"[錯誤] 無法連線到 Server: {e}")
            sys.exit(1)

    def register(self):
        """註冊功能"""
        print("\n=== 註冊開發者帳號 ===")
        username = input("請輸入帳號: ").strip()
        password = input("請輸入密碼: ").strip()
        
        if not username or not password:
            print("帳號密碼不能為空！")
            return

        # 1. 準備請求資料
        request = {
            "action": "REGISTER",
            "username": username,
            "password": password,
            "role": "developer"  # 明確指定這是開發者
        }
        
        # 2. 發送與接收
        send_json(self.sock, request)
        response = recv_json(self.sock)
        
        # 3. 顯示結果
        print(f"[{response['status']}] {response['message']}")

    def login(self):
        """登入功能"""
        print("\n=== 登入 ===")
        username = input("請輸入帳號: ").strip()
        password = input("請輸入密碼: ").strip()

        request = {
            "action": "LOGIN",
            "username": username,
            "password": password
        }
        
        send_json(self.sock, request)
        response = recv_json(self.sock)
        
        if response['status'] == 'SUCCESS':
            print(f"登入成功！歡迎 {username}")
            self.user_data = response['user']
            # 登入成功後，可以進入「已登入選單」，這裡我們先簡單處理
        else:
            print(f"登入失敗: {response['message']}")

    def start(self):
        """主程式迴圈 (Menu)"""
        self.connect()
        
        while True:
            # 根據是否登入顯示不同選單
            if not self.user_data:
                print("\n=== Game Store (開發者端) ===")
                print("1. 註冊帳號")
                print("2. 登入系統")
                print("3. 離開")
                choice = input("請選擇 (1-3): ").strip()

                if choice == '1':
                    self.register()
                elif choice == '2':
                    self.login()
                elif choice == '3':
                    print("Bye!")
                    break
                else:
                    print("無效的選項，請重新輸入。")
            else:
                # 已登入狀態的選單 (之後會在這裡加上「上架遊戲」)
                print(f"\n=== 開發者後台 ({self.user_data['username']}) ===")
                print("1. 上架新遊戲 (尚未實作)")
                print("2. 登出")
                choice = input("請選擇 (1-2): ").strip()

                if choice == '1':
                    print("功能開發中...")
                elif choice == '2':
                    self.user_data = None  # 清除登入狀態
                    print("已登出")
                else:
                    print("無效的選項")

        self.sock.close()

if __name__ == "__main__":
    client = DevClient()
    client.start()