# player/player_client.py
import socket
import sys
import os
import subprocess
import time

# --- 路徑設定 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from common.protocol import send_json, recv_json
from common.constant import SERVER_PORT

# 預設 IP (開發時用 localhost)
SERVER_IP = '127.0.0.1'

class PlayerClient:
    def __init__(self):
        self.sock = None
        self.user_data = None

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((SERVER_IP, SERVER_PORT))
            print("[系統] 已連線到大廳")
        except:
            print("[錯誤] 無法連線到 Server")
            sys.exit(1)

    def start_game_subprocess(self, game_id, ip, port):
        """啟動遊戲 (run.py)"""
        # 正式版路徑應為: player/downloads/{username}/{game_id}/run.py
        # 測試版路徑直接指向: server/uploaded_games/{game_id}/run.py
        
        game_path = os.path.join(parent_dir, "server", "uploaded_games", game_id, "run.py")
        
        if not os.path.exists(game_path):
            print(f"[錯誤] 找不到遊戲檔案: {game_path}")
            return

        # 組合啟動指令
        cmd = [
            sys.executable, 
            game_path,
            self.user_data['username'],
            ip,
            str(port)
        ]
        print(f"[系統] 啟動遊戲中... {cmd}")
        subprocess.Popen(cmd) # 開新視窗執行

    def main_menu(self):
        self.connect()
        while True:
            print("\n=== 遊戲大廳 ===")
            if not self.user_data:
                print("1. 註冊")
                print("2. 登入")
                print("3. 離開")
                choice = input("輸入選項: ")
                if choice == '1': self.register()
                elif choice == '2': self.login()
                elif choice == '3': break
            else:
                print(f"玩家: {self.user_data['username']}")
                print("1. 瀏覽遊戲列表")
                print("2. 建立房間 (當房主)")
                print("3. 加入房間 (當挑戰者)")
                print("4. 登出")
                choice = input("輸入選項: ")
                
                if choice == '1': self.list_games()
                elif choice == '2': self.create_room()
                elif choice == '3': self.join_room()
                elif choice == '4': self.user_data = None

    def register(self):
        u = input("帳號: ")
        p = input("密碼: ")
        send_json(self.sock, {"action": "REGISTER", "username": u, "password": p})
        print("Server回覆:", recv_json(self.sock).get('message'))

    def login(self):
        u = input("帳號: ")
        p = input("密碼: ")
        send_json(self.sock, {"action": "LOGIN", "username": u, "password": p})
        res = recv_json(self.sock)
        if res['status'] == 'SUCCESS':
            print("登入成功！")
            self.user_data = res['user']
        else:
            print("登入失敗:", res.get('message'))

    def list_games(self):
        send_json(self.sock, {"action": "LIST_GAMES"})
        res = recv_json(self.sock)
        print("可用遊戲:", res.get('games'))

    def create_room(self):
        gid = input("請輸入要玩的遊戲ID (如 Tetris): ")
        send_json(self.sock, {"action": "CREATE_ROOM", "game_id": gid})
        res = recv_json(self.sock)
        if res['status'] == 'SUCCESS':
            print(f"建立成功！房間ID: {res['room_id']}")
            print("請等待挑戰者加入... (注意：目前尚未實作房主自動跳轉，請用挑戰者視窗測試)")
        else:
            print("建立失敗:", res.get('message'))

    def join_room(self):
        rid = input("請輸入房間ID: ")
        send_json(self.sock, {"action": "JOIN_ROOM", "room_id": rid})
        res = recv_json(self.sock)
        
        if res['status'] == 'SUCCESS':
            print("加入成功！")
            if res.get('game_start'):
                print("遊戲開始！啟動中...")
                self.start_game_subprocess(res['game_id'], res['game_ip'], res['game_port'])
        else:
            print("加入失敗:", res.get('message'))

if __name__ == "__main__":
    client = PlayerClient()
    client.main_menu()