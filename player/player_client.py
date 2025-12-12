# player/player_client.py
import socket
import sys
import os
import subprocess
import time
import zipfile
import io
import json

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

    # === 核心功能：版本管理與自動下載 (RQU-5 P2, P3) ===

    def get_local_version(self, game_id):
        """讀取本地已下載遊戲的版本號 (由 game_config.json 讀取)"""
        path = os.path.join(parent_dir, "downloads", self.user_data['username'], game_id, "game_config.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get("version")
        except:
            return None

    def ensure_latest_version(self, game_id, server_version):
        """強制檢查版本：若本地版本不符或未安裝，則自動觸發下載 (符合 P2)"""
        local_ver = self.get_local_version(game_id)
        
        if local_ver is None:
            print(f"[系統] 偵測到未安裝 {game_id}，開始自動下載...")
            return self.download_game(game_id)
        elif local_ver != server_version:
            print(f"[系統] 偵測到新版本 (本地:{local_ver} -> 雲端:{server_version})，正在強制更新...")
            return self.download_game(game_id)
        else:
            print(f"[系統] 檔案版本校驗通過 (v{local_ver})")
            return os.path.join(parent_dir, "downloads", self.user_data['username'], game_id)

    def download_game(self, game_id):
        """從伺服器下載 ZIP 並解壓到玩家隔離區"""
        send_json(self.sock, {"action": "DOWNLOAD", "game_id": game_id})
        res = recv_json(self.sock)
        
        if res['status'] == 'SUCCESS':
            file_size = res['size']
            file_data = bytearray()
            while len(file_data) < file_size:
                chunk = recv_frame(self.sock)
                file_data.extend(chunk)
            
            # 存放到 downloads/{username}/{game_id}
            download_dir = os.path.join(parent_dir, "downloads", self.user_data['username'], game_id)
            if not os.path.exists(download_dir):
                os.makedirs(download_dir)
            
            with zipfile.ZipFile(io.BytesIO(file_data)) as zf:
                zf.extractall(download_dir)
            print(f"[系統] {game_id} 下載/更新完成。")
            return download_dir
        else:
            print(f"[錯誤] 下載失敗: {res.get('message')}")
            return None

    # === 商城與評價功能 (RQU-5 P1, RQU-6 P4) ===

    def list_games(self):
        """顯示遊戲商城清單"""
        send_json(self.sock, {"action": "LIST_GAMES"})
        res = recv_json(self.sock)
        if res['status'] == 'SUCCESS':
            games = res.get('games', [])
            print("\n=== 遊戲商城 (Store) ===")
            if not games: print("目前商城沒有上架遊戲。"); return
            
            for i, g in enumerate(games):
                avg_rating = f"{g['avg_rating']:.1f}" if g.get('avg_rating') else "尚無"
                print(f"{i+1}. {g['name']} [★ {avg_rating}]")

            choice = input("\n請輸入編號查看詳情 (輸入 q 返回): ").strip()
            if choice.lower() == 'q': return
            try:
                self.show_game_detail(games[int(choice)-1])
            except: print("無效選擇")

    def show_game_detail(self, game):
        """顯示遊戲詳細資訊與玩家評價 (符合 P1 要求)"""
        print(f"\n--- {game['name']} 詳情 ---")
        print(f"作者: {game['author_username']} | 最新版本: {game['version']}")
        print(f"遊戲簡介: {game['description']}")
        print(f"目前評分: {game['avg_rating'] or '尚無'} ({game['review_count'] or 0} 則評論)")

        while True:
            print("\n[1] 建立房間 [2] 撰寫評價 [3] 查看所有評論 [q] 返回")
            c = input("請輸入選擇: ").strip()
            if c == '1':
                # 建立房間前強制檢查版本
                self.ensure_latest_version(game['name'], game['version'])
                self.create_room(game['name'])
                break
            elif c == '2':
                self.write_review(game['name'])
            elif c == '3':
                self.view_reviews(game['name'])
            elif c.lower() == 'q':
                break

    def view_reviews(self, game_name):
        send_json(self.sock, {"action": "GET_REVIEWS", "game_name": game_name})
        res = recv_json(self.sock)
        print(f"\n--- {game_name} 評論列表 ---")
        for r in res.get('reviews', []):
            print(f"[{r['username']}] ★{r['rating']}: {r['comment']}")

    def write_review(self, game_name):
        """RQU-6: 撰寫評分與留言"""
        print(f"\n=== 對 {game_name} 發表評價 ===")
        try:
            rating = int(input("評分 (1-5 分): "))
            if not 1 <= rating <= 5: raise ValueError
            comment = input("評論文字: ").strip()
            
            send_json(self.sock, {
                "action": "SUBMIT_REVIEW", 
                "game_name": game_name, 
                "rating": rating, 
                "comment": comment
            })
            res = recv_json(self.sock)
            print(f"[{res['status']}] {res['message']}")
        except ValueError:
            print("[錯誤] 評分請輸入 1 到 5 之間的整數。")

    # === 房間管理 (解決返回機制與列表問題) ===

    def start_game_subprocess(self, game_id, ip, port):
        time.sleep(1.5)
        """啟動解壓後的遊戲 run.py"""
        game_dir = os.path.join(parent_dir, "downloads", self.user_data['username'], game_id)
        script_path = os.path.join(game_dir, "run.py")
        
        if os.path.exists(script_path):
            print(f"\n[啟動] 正在連線至 {ip}:{port}")
            time.sleep(1) # 給伺服器一點啟動時間
            # 關鍵：cwd=game_dir 讓 run.py 能正確 import 自己的 protocol.py
            subprocess.Popen([sys.executable, script_path, self.user_data['username'], ip, str(port)], cwd=game_dir)
        else:
            print(f"[錯誤] 找不到啟動檔: {script_path}")

    def list_rooms(self):
        """瀏覽房間列表，解決玩家看不到房號的問題"""
        send_json(self.sock, {"action": "LIST_ROOMS"})
        res = recv_json(self.sock)
        rooms = res.get('rooms', [])
        print("\n=== 目前可加入房間 ===")
        if not rooms: print("目前無房間，快去建立一個吧！"); return

        for r in rooms:
            print(f"房號: {r['room_id']} | 遊戲: {r['game_id']} | 人數: {r['player_count']}/2 | 狀態: {r['status']}")
        
        rid = input("\n請輸入房間 ID 加入 (輸入 q 返回): ").strip()
        if rid.lower() == 'q' or not rid: return
        self.join_room(rid)

    def create_room(self, pre_gid=None):
        """房主建立房間並在此等待 (Stay in room)"""
        gid = pre_gid or input("請輸入遊戲名稱 (輸入 q 返回): ").strip()
        if gid.lower() == 'q' or not gid: return

        # 1. 建立房間前先拿遊戲資訊以確保版本 (RQU-5 P2)
        send_json(self.sock, {"action": "LIST_GAMES"})
        games_res = recv_json(self.sock)
        target_game = next((g for g in games_res['games'] if g['name'] == gid), None)
        if not target_game:
            print(f"[錯誤] 找不到遊戲: {gid}"); return
        
        # 強制版本檢查
        self.ensure_latest_version(gid, target_game['version'])

        # 2. 發送建立房間指令
        send_json(self.sock, {"action": "CREATE_ROOM", "game_id": gid})
        res = recv_json(self.sock)
        
        if res['status'] == 'SUCCESS':
            room_id = res['room_id']
            print(f"\n[房主] 房間 ID: {room_id} 建立成功！")
            print("正在等待挑戰者加入... (按 Ctrl+C 取消等待)")

            # ★ 關鍵修正：進入等待迴圈，不要讓函式結束
            try:
                while True:
                    time.sleep(1) # 每秒檢查一次
                    send_json(self.sock, {"action": "CHECK_ROOM", "room_id": room_id})
                    check_res = recv_json(self.sock)

                    if check_res.get("game_start"):
                        print("\n[系統] 挑戰者已加入！正在最終校驗版本...")
                        # 房主在啟動前再次確認版本
                        self.ensure_latest_version(check_res['game_id'], check_res['version'])
                        
                        print("[啟動] 正在連線至遊戲伺服器...")
                        self.start_game_subprocess(
                            check_res['game_id'], 
                            check_res['game_ip'], 
                            check_res['game_port']
                        )
                        break # 遊戲開始，跳出迴圈
                    
                    elif check_res.get("status") == "FAIL":
                        print("\n[錯誤] 房間已被關閉或失效。")
                        break
                    else:
                        # 顯示目前人數 (動畫效果)
                        players = check_res.get("players", [])
                        sys.stdout.write(f"\r目前人數: {len(players)}/2 ...")
                        sys.stdout.flush()
            except KeyboardInterrupt:
                print("\n[系統] 已取消等待房間。")
        else:
            print(f"[失敗] {res.get('message')}")

    def join_room(self, room_id):
        """實作缺失的 join_room 函式 (RQU-5 P3 自動化下載)"""
        send_json(self.sock, {"action": "JOIN_ROOM", "room_id": room_id})
        res = recv_json(self.sock)
        
        if res['status'] == 'SUCCESS':
            print("加入成功！正在校驗遊戲版本...")
            # 確保最新版本 (由 Server 回傳的資訊進行檢查)
            self.ensure_latest_version(res['game_id'], res['version'])
            
            if res.get('game_start'):
                print("遊戲啟動中...")
                self.start_game_subprocess(res['game_id'], res['game_ip'], res['game_port'])
        else:
            print("加入失敗:", res.get('message'))

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
                print(f"\n=== 玩家大廳 ({self.user_data['username']}) ===")
                print("1. 瀏覽遊戲商城\n2. 瀏覽房間列表\n3. 建立遊戲房間\n4. 登出")
                c = input("請選擇: ").strip()
                if c == '1': self.list_games()
                elif c == '2': self.list_rooms()
                elif c == '3': self.create_room()
                elif c == '4': self.user_data = None; print("已登出")

if __name__ == "__main__":
    client = PlayerClient()
    client.main_menu()