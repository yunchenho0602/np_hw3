import socket
import sys
import os
import json
import zipfile
import io
import time
import shutil

# --- 路徑設定 ---
# 讓 client 能找到上一層的 common
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# --- Import ---
# 注意：這裡多 import 了 send_frame，因為傳檔案需要用到
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
        else:
            print(f"登入失敗: {response['message']}")

    def upload_game(self):
        """符合 Use Case D1 的互動式上傳流程"""
        workspace = os.path.join(parent_dir, "my_games_src")
        if not os.path.exists(workspace): os.makedirs(workspace)

        # 1. Step 3: 選擇要上傳的位置 (清單顯示)
        projects = [f for f in os.listdir(workspace) if os.path.isdir(os.path.join(workspace, f))]
        if not projects:
            print("工作區沒有專案，請先選擇 '建立新遊戲專案'。"); return

        print("\n--- 選擇要上傳的本地專案 ---")
        for i, p in enumerate(projects): print(f"{i+1}. {p}")
        try:
            folder_name = projects[int(input("請輸入序號: ")) - 1]
        except: return
        source_dir = os.path.join(workspace, folder_name)

        # 2. Step 4: 由配置檔讀取預設資訊
        config = {"game_name": folder_name, "version": "1.0.0", "description": "", "max_players": 2}
        config_path = os.path.join(source_dir, "game_config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config.update(json.load(f))

        # 3. Step 3 & 5: 互動式引導輸入與確認
        print("\n=== 請確認/修改上架資訊 (直接按 Enter 沿用預設值) ===")
        g_name = input(f"遊戲名稱 [{config['game_name']}]: ").strip() or config['game_name']
        g_desc = input(f"遊戲描述 [{config['description']}]: ").strip() or config['description']
        g_ver  = input(f"版本號碼 [{config['version']}]: ").strip() or config['version']
        
        print(f"\n[待上架預覽]\n名稱: {g_name}\n描述: {g_desc}\n版本: {g_ver}")
        if input("確認上傳到商城？(y/n): ").lower() != 'y': return

        # 4. Step 6: 系統打包與傳輸
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(source_dir):
                for file in files:
                    zf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), source_dir))
        
        zip_data = memory_file.getvalue()
        send_json(self.sock, {
            "action": "UPLOAD", "game_name": g_name, "version": g_ver,
            "description": g_desc, "filename": f"{folder_name}.zip", "size": len(zip_data)
        })
        
        if recv_json(self.sock).get('status') == 'READY':
            send_frame(self.sock, zip_data)
            print(recv_json(self.sock).get('message'))
    def view_my_games(self):
            """查看已上架遊戲 (符合 PDF Step 7)"""
            send_json(self.sock, {"action": "LIST_MY_GAMES"})
            res = recv_json(self.sock)
            if res['status'] == 'SUCCESS':
                print("\n=== 我的遊戲列表 ===")
                games = res.get('games', [])
                if not games:
                    print("目前沒有已上架的遊戲。")
                else:
                    for g in games:
                        print(f"- {g['name']} (v{g['version']}): {g['description']}")
            else:
                print("取得列表失敗。")
    
    def create_new_project(self):
        """整合進介面的範本建立功能 (符合無須額外指令規定)"""
        print("\n=== 建立新遊戲專案 (Scaffolding) ===")
        new_game_name = input("請輸入新遊戲的資料夾名稱: ").strip()
        if not new_game_name: return

        template_dir = os.path.join(parent_dir, "template")
        workspace_dir = os.path.join(parent_dir, "my_games_src")
        target_dir = os.path.join(workspace_dir, new_game_name)

        if not os.path.exists(template_dir):
            print("[錯誤] 找不到範本資料夾，請確保 'template/' 存在於根目錄。"); return
        if os.path.exists(target_dir):
            print(f"[錯誤] 專案 '{new_game_name}' 已存在。"); return

        try:
            shutil.copytree(template_dir, target_dir)
            # 自動初始化 config.json
            config_path = os.path.join(target_dir, "game_config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                config["game_name"] = new_game_name
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
            print(f"[成功] 專案已建立於: {target_dir}")
        except Exception as e:
            print(f"[錯誤] 建立失敗: {e}")

    def start(self):
        """主程式迴圈 (Menu)"""
        self.connect()
        
        while True:
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
                    print("無效的選項")
            else:
                print(f"\n=== 開發者後台 ({self.user_data['username']}) ===")
                print("1. 上架新遊戲")
                print("2. 查看我的遊戲列表")
                print("3. 建立新遊戲專案 (Template)") # 新增選項
                print("4. 登出")
                choice = input("請選擇: ")

                if choice == '1': self.upload_game()
                elif choice == '2': self.view_my_games()
                elif choice == '3': self.create_new_project() # 呼叫新功能
                elif choice == '4': break
                else:
                    print("無效的選項")

        self.sock.close()

if __name__ == "__main__":
    client = DevClient()
    client.start()