import socket
import sys
import os
import json
import zipfile
import io
import time
import shutil

# --- 路徑設定 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(current_dir)
sys.path.append(parent_dir)

# --- Import ---
from common.protocol import send_json, recv_json, send_frame
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
        send_json(self.sock, {"action": "REGISTER", "username": username, "password": password, "role": "developer"})
        response = recv_json(self.sock)
        print(f"[{response['status']}] {response['message']}")

    def login(self):
        """登入功能"""
        print("\n=== 登入 ===")
        username = input("帳號: ").strip()
        password = input("密碼: ").strip()
        send_json(self.sock, {"action": "LOGIN", "username": username, "password": password})
        response = recv_json(self.sock)
        if response['status'] == 'SUCCESS':
            print(f"登入成功！歡迎 {username}")
            self.user_data = response['user']
        else:
            print(f"登入失敗: {response['message']}")

    def create_new_project(self):
        from create_game_template import create_game
        print("\n=== 建立新遊戲專案 ===")
        name = input("請輸入新遊戲名稱: ").strip()
        if not name:
            print("名稱不能為空！")
            return
        
        create_game(name)
        print(f"[完成] 已建立新遊戲專案：{name}")

    def upload_game(self):
        """符合 Use Case D1 的互動式上傳流程"""
        workspace = os.path.join(current_dir, "game")
        if not os.path.exists(workspace): os.makedirs(workspace)

        projects = [f for f in os.listdir(workspace) if os.path.isdir(os.path.join(workspace, f))]
        if not projects:
            print("工作區沒有專案，請先選擇 '建立新遊戲專案'。"); return

        print("\n--- 選擇要上傳的本地專案 ---")
        for i, p in enumerate(projects): print(f"{i+1}. {p}")
        try:
            folder_name = projects[int(input("請輸入序號: ")) - 1]
        except: return
        source_dir = os.path.join(workspace, folder_name)

        # 讀取配置檔
        config = {"game_name": folder_name, "version": "1.0.0", "description": ""}
        config_path = os.path.join(source_dir, "game_config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config.update(json.load(f))

        print("\n=== 請輸入/確認上架資訊 (直接按 Enter 使用預設值) ===")
        g_name = input(f"遊戲名稱 [{config['game_name']}]: ").strip() or config['game_name']
        g_desc = input(f"遊戲描述 [{config['description']}]: ").strip() or config['description']
        g_ver  = input(f"版本號碼 [{config['version']}]: ").strip() or config['version']
        max_p = input(f"最大玩家人數 (預設 2): ").strip() or "2"
        
        print(f"\n[待上架預覽]\n名稱: {g_name}\n描述: {g_desc}\n版本: {g_ver}")
        if input("確認上傳？(y/n): ").lower() != 'y': return

        self._send_zip_payload(source_dir, g_name, g_ver, g_desc, folder_name, "UPLOAD", max_players=int(max_p))

    def update_game_flow(self):
        """實作 RQU-4：更新遊戲版本"""
        send_json(self.sock, {"action": "LIST_MY_GAMES"})
        res = recv_json(self.sock)
        my_games = res.get('games', [])
        if not my_games: print("你目前沒有上架中的遊戲。"); return

        print("\n--- 選擇要更新的遊戲 ---")
        for i, g in enumerate(my_games): print(f"{i+1}. {g['name']} (目前 v{g['version']})")
        try:
            idx = int(input("序號: ")) - 1
            target_game = my_games[idx]['name']
            curr_ver = my_games[idx]['version']
        except:
            print("無效的選擇")
            return

        parts = curr_ver.split('.')
        try:
            # 嘗試將最後一位數字加 1
            parts[-1] = str(int(parts[-1]) + 1)
            suggested_ver = ".".join(parts)
        except (ValueError, IndexError):
            # 若無法解析為數字，則預設建議原版本號
            suggested_ver = curr_ver

        workspace = os.path.join(current_dir, "game")
        source_dir = os.path.join(workspace, target_game)
        if not os.path.exists(source_dir):
            print(f"[錯誤] 本地找不到專案資料夾 {target_game}，無法打包更新。"); return

        print(f"\n=== 更新遊戲: {target_game} ===")
        new_ver = input(f"新版本號 [預設建議 {suggested_ver}]: ").strip() or suggested_ver
        
        new_desc = input("更新說明 (留空則保留原描述): ").strip()

        # 若有輸入，附加到原描述後面
        if new_desc:
            merged_desc = f"{my_games[idx]['description']}\n\n[更新 {new_ver}]\n{new_desc}"
        else:
            merged_desc = my_games[idx]['description']


        # 確認時就會看到正確的版本號了
        if input(f"確認更新 {target_game} 至 v{new_ver}？(y/n): ").lower() != 'y': 
            return
        
        current_max_p = my_games[idx].get('max_players', 2)
        new_max_p_input = input(f"修改最大人數 [目前 {current_max_p}]: ").strip() or str(current_max_p)
        new_max_p = int(new_max_p_input)

        self._send_zip_payload(source_dir, target_game, new_ver, merged_desc, target_game, "UPDATE_GAME", max_players=new_max_p)

    def remove_game_flow(self):
        """實作 RQU-4：下架遊戲"""
        send_json(self.sock, {"action": "LIST_MY_GAMES"})
        res = recv_json(self.sock)
        my_games = res.get('games', [])
        if not my_games: return

        print("\n--- 選擇要下架的遊戲 ---")
        for i, g in enumerate(my_games): print(f"{i+1}. {g['name']}")
        try:
            target_game = my_games[int(input("序號: ")) - 1]['name']
        except: return

        if input(f"確定要永久下架 {target_game} 嗎？此操作不可逆 (y/n): ").lower() == 'y':
            send_json(self.sock, {"action": "DELETE_GAME", "game_name": target_game})
            print(recv_json(self.sock).get('message'))

    def _send_zip_payload(self, source_dir, g_name, g_ver, g_desc, folder_name, action, max_players=2):
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(source_dir):
                for file in files:
                    zf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), source_dir))
        
        zip_data = memory_file.getvalue()
        
        payload = {
            "action": action, 
            "game_name": g_name, 
            "version": g_ver,
            "description": g_desc, 
            "filename": f"{folder_name}.zip", 
            "size": len(zip_data),
            "max_players": max_players 
        }
        
        send_json(self.sock, payload)
        
        res = recv_json(self.sock)
        if res.get('status') == 'READY':
            send_frame(self.sock, zip_data)
            final_res = recv_json(self.sock)
            print(final_res.get('message'))
        else:
            print(f"[失敗] 伺服器拒絕上傳: {res.get('message')}")

    def view_my_games(self):
        send_json(self.sock, {"action": "LIST_MY_GAMES"})
        res = recv_json(self.sock)
        print("\n=== 我的遊戲列表 ===")
        games = res.get('games', [])
        if not games: print("目前沒有已上架的遊戲。")
        else:
            for g in games: print(f"- {g['name']} (v{g['version']}): {g['description']}")

    def start(self):
        self.connect()
        while True:
            if not self.user_data:
                print("\n=== Game Store (開發者端) ===")
                print("1. 註冊帳號\n2. 登入系統\n3. 離開")
                choice = input("請選擇: ").strip()
                if choice == '1': self.register()
                elif choice == '2': self.login()
                elif choice == '3': break
            else:
                print(f"\n=== 開發者後台 ({self.user_data['username']}) ===")
                print("1. 查看我的遊戲列表")
                print("2. 上架新遊戲")
                print("3. 更新遊戲版本")
                print("4. 下架遊戲")
                print("5. 建立新專案 (Template)")
                print("6. 登出")
                c = input("請選擇: ").strip()
                if c == '1':self.view_my_games()
                elif c == '2': self.upload_game()
                elif c == '3': self.update_game_flow()
                elif c == '4': self.remove_game_flow()
                elif c == '5': self.create_new_project()
                elif c == '6': self.user_data = None; print("已登出")

if __name__ == "__main__":
    DevClient().start()