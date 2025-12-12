# player/player_client.py
import socket
import sys
import os
import subprocess
import time
import zipfile
import io

# --- 路徑設定 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from common.protocol import send_json, recv_json, recv_frame
from common.constant import SERVER_PORT, SERVER_IP

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

    def download_game(self, game_id):
        """實作從伺服器下載 ZIP 並解壓縮到玩家獨立資料夾"""
        print(f"[系統] 正在從伺服器請求遊戲檔案: {game_id}")
        
        # 1. 發送下載請求
        send_json(self.sock, {"action": "DOWNLOAD", "game_id": game_id})
        
        # 2. 接收伺服器回應
        res = recv_json(self.sock)
        if res['status'] == 'SUCCESS':
            file_size = res['size']
            print(f"[系統] 準備接收檔案 ({file_size} bytes)...")
            
            # 3. 接收二進制數據
            file_data = bytearray()
            while len(file_data) < file_size:
                chunk = recv_frame(self.sock)
                if not chunk: break
                file_data.extend(chunk)
                # 顯示簡單進度
                sys.stdout.write(".")
                sys.stdout.flush()
            
            # 4. 定義存放路徑: downloads/{username}/{game_id}/
            # 使用 parent_dir 確保在專案根目錄下的 downloads
            player_download_root = os.path.join(parent_dir, "downloads", self.user_data['username'], game_id)
            if not os.path.exists(player_download_root):
                os.makedirs(player_download_root)
            
            # 5. 解壓縮
            print(f"\n[系統] 正在解壓縮至 {player_download_root}")
            with zipfile.ZipFile(io.BytesIO(file_data)) as zf:
                zf.extractall(player_download_root)
            
            return player_download_root
        else:
            print(f"[錯誤] 下載失敗: {res.get('message')}")
            return None

    def start_game_subprocess(self, game_id, ip, port):
        """修改後的啟動邏輯：先下載，再執行本地檔案"""
        # --- 關鍵修改：先下載遊戲包 ---
        local_dir = self.download_game(game_id)
        if not local_dir:
            print("[錯誤] 無法啟動遊戲，因為檔案下載失敗。")
            return

        # --- 執行下載後的 run.py ---
        game_path = os.path.join(local_dir, "run.py")
        
        if not os.path.exists(game_path):
            print(f"[錯誤] 下載的包中找不到啟動檔 run.py: {game_path}")
            return

        # 組合啟動指令 (配合 sys.argv)
        cmd = [
            sys.executable, 
            game_path,
            self.user_data['username'],
            ip,
            str(port)
        ]
        print(f"[系統] 正在啟動本地遊戲實例: {cmd}")
        subprocess.Popen(cmd)
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
            room_id = res['room_id']
            print(f"建立成功！房間ID: {room_id}")
            print("請等待挑戰者加入... (注意：目前尚未實作房主自動跳轉，請用挑戰者視窗測試)")
            try :
                while True :
                    time.sleep(1)
                    send_json(self.sock, {"action":"CHECK_ROOM", "room_id":room_id})
                    check_res = recv_json(self.sock)

                    if check_res.get("game_start") :
                        print("挑戰者已加入！遊戲啟動中...")
                        self.start_game_subprocess(
                            check_res['game_id'], 
                            check_res['game_ip'], 
                            check_res['game_port']
                        )
                        break
                    elif check_res.get("status") == "FAIL":
                        print("房間已失效")
                        break
                    else :
                        players = check_res.get("players", [])
                        sys.stdout.write(f"\r目前人數: {len(players)}/2")
                        sys.stdout.flush()
            except KeyboardInterrupt:
                print("\n取消等待")
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