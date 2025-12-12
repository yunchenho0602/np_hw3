import socket
import threading
import json
import sys
import os
import subprocess
import shutil
import zipfile

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# --- Import 自訂模組 ---
from common.protocol import send_json, recv_json, recv_frame
from common.constant import SERVER_PORT, SERVER_IP
from db_server import register_user, login_check, add_game, get_games_by_author

# --- Server 設定 ---
HOST = '0.0.0.0'  # 監聽所有網卡 (讓別人也能連進來)
PORT = SERVER_PORT

rooms = {}
room_id_counter = 100
rooms_lock = threading.Lock()

def start_game_process(game_id, room_id):
    temp_sock = socket.socket()
    temp_sock.bind(('', 0))
    game_port = temp_sock.getsockname()[1]
    temp_sock.close()

    game_dir = os.path.join("server", "uploaded_game", game_id)
    server_script = os.path.join(game_dir, "game_server.py")

    cmd = [sys.executable, server_script, str(game_port), str(room_id)]
    print(f"[Server] 正在啟動遊戲 Server, Port: {game_port}")
    subprocess.Popen(cmd)

    return game_port

def handle_client(conn, addr):
    """
    處理單一 Client 的所有請求 (執行緒函式)
    """
    global room_id_counter
    print(f"[連線] 新連線來自: {addr}")
    
    user_data = None  # 用來紀錄目前連線的使用者是誰 (登入後才有值)

    try:
        while True:
            # 1. 等待並接收 Client 傳來的 JSON 指令
            request = recv_json(conn)
            
            # 如果收到空資料或連線斷開
            if not request:
                break
                
            print(f"[收到指令] {addr}: {request}")
            
            action = request.get("action")
            response = {"status": "FAIL", "message": "Unknown action"}

            # --- 2. 根據 action 決定要做什麼 (路由分發) ---
            
            # === 功能 A: 註冊 ===
            if action == "REGISTER":
                username = request.get("username")
                password = request.get("password")
                role = request.get("role", "player") # 預設是玩家
                
                if register_user(username, password, role):
                    response = {"status": "SUCCESS", "message": "註冊成功"}
                else:
                    response = {"status": "FAIL", "message": "帳號已存在"}

            # === 功能 B: 登入 ===
            elif action == "LOGIN":
                username = request.get("username")
                password = request.get("password")
                
                user = login_check(username, password)
                if user:
                    user_data = user
                    response = {
                        "status": "SUCCESS", 
                        "message": "登入成功",
                        "user": {"username": user['username'], "role": user['role']}
                    }
                else:
                    response = {"status": "FAIL", "message": "帳號或密碼錯誤"}

            # === 其他未完成功能 (先留空) ===
            elif action == "LIST_GAMES":
                games_dir = os.path.join(current_dir, "uploaded_game")
                if not os.path.exists(games_dir): os.makedirs(games_dir)
                # 列出資料夾名稱當作 Game ID
                game_list = [f for f in os.listdir(games_dir) if os.path.isdir(os.path.join(games_dir, f))]
                response = {"status": "SUCCESS", "games": game_list}

            # --- 4. 建立房間 ---
            elif action == "CREATE_ROOM":
                if user_data:
                    game_id = request.get("game_id")
                    with rooms_lock:
                        rid = str(room_id_counter)
                        room_id_counter += 1
                        rooms[rid] = {
                            "game_id": game_id,
                            "players": [user_data['username']],
                            "max_players": 2 # 暫時寫死
                        }
                    response = {"status": "SUCCESS", "room_id": rid, "message": "房間建立成功"}
                else:
                    response = {"status": "FAIL", "message": "請先登入"}

            # --- 5. 加入房間 ---
            elif action == "JOIN_ROOM":
                if user_data:
                    rid = request.get("room_id")
                    with rooms_lock:
                        if rid in rooms:
                            room = rooms[rid]
                            if len(room["players"]) < room["max_players"]:
                                room["players"].append(user_data['username'])
                                response = {"status": "SUCCESS", "message": "加入成功"}
                                
                                # 檢查是否滿房 -> 開始遊戲
                                if len(room["players"]) == room["max_players"]:
                                    print(f"[Server] 房間 {rid} 滿員，開始遊戲！")
                                    port = start_game_process(room["game_id"], rid)

                                    room["game_port"] = port
                                    room["status"] = "PLAYING"
                                    
                                    # 回傳開始資訊給觸發者
                                    response["game_start"] = True
                                    response["game_ip"] = SERVER_IP # 在 Demo 時通常是 localhost
                                    response["game_port"] = port
                                    response["game_id"] = room["game_id"]
                            else:
                                response = {"status": "FAIL", "message": "房間已滿"}
                        else:
                            response = {"status": "FAIL", "message": "房間不存在"}
                else:
                    response = {"status": "FAIL", "message": "請先登入"}
            
            elif action =="CHECK_ROOM" :
                rid = request.get("room_id")
                with rooms_lock:
                    if rid in rooms :
                        room = rooms[rid]
                        if "game_port" in room:
                            response = {
                                "status": "SUCCESS",
                                "game_start": True,
                                "game_ip": SERVER_IP,
                                "game_port": room["game_port"],
                                "game_id": room["game_id"]
                            }
                        else :
                            response = {
                                "status" : "WAITING",
                                "players" : room["players"]
                            }
                    else :
                        response = {
                            "status" : "FAIL",
                            "message" : "房間已關閉"
                        }
            elif action == "LIST_ROOM" :
                if not user_data :
                    response = {"status":"FAIL", "message":"請先登入"}
                else :
                    room_list = []
                    with rooms_lock :
                        for rid, r in rooms.items():
                            if "game_port" not in r :
                                room_list.append({
                                    "room_id":rid,
                                    "game_id":r["game_id"],
                                    "players":len(r["players"]),
                                    "max":r["max_players"],
                                    "host":r["host"]
                                })
                    response = {"status":"SUCCESS", "rooms":room_list}
            
            elif action == "DOWNLOAD" :
                game_id = request.get("game_id")
                zip_path = os.path.join(current_dir, "uploaded_game", f"{game_id}.zip")

                if os.path.exists(zip_path) :
                    file_size = os.path.getsize(zip_path)
                    send_json(conn, {"status":"SUCCESS", "size":file_size})

                    from common.protocol import send_frame
                    with open(zip_path, "rb") as f:
                        while True :
                            chunk = f.read(60000)
                            if not chunk :
                                break
                            send_frame(conn, chunk)
                    print(f"[Server] 已傳送遊戲檔案: {game_id}")
                else :
                    send_json(conn, {"status":"FAIL", "message":"找不到遊戲檔案"})

            elif action == "UPLOAD":
                if not user_data or user_data['role'] != 'developer':
                    send_json(conn, {"status": "FAIL", "message": "權限不足"})
                    continue

                game_name = request.get("game_name")
                version = request.get("version")
                desc = request.get("description")
                filename = request.get("filename")
                file_size = request.get("size")

                # 1. 準備接收檔案
                zip_path = os.path.join(current_dir, "uploaded_game", filename)
                send_json(conn, {"status": "READY"})
                
                try:
                    with open(zip_path, "wb") as f:
                        received = 0
                        while received < file_size:
                            chunk = recv_frame(conn)
                            if not chunk: break
                            f.write(chunk)
                            received += len(chunk)
                    
                    # 2. 寫入資料庫 (符合 PDF Step 6)
                    # 我們將 zip 檔名作為路徑存入
                    if add_game(game_name, version, desc, filename, user_data['username']):
                        response = {"status": "SUCCESS", "message": f"遊戲 {game_name} 上架成功"}
                    else:
                        response = {"status": "FAIL", "message": "資料庫寫入失敗"}
                except Exception as e:
                    response = {"status": "FAIL", "message": f"上傳中斷: {e}"}

            elif action == "LIST_MY_GAMES":
                # 取得該開發者的遊戲 (符合 PDF Step 7)
                my_games = get_games_by_author(user_data['username'])
                response = {"status": "SUCCESS", "games": my_games}

            # server/server.py 處理 Action 的部分

            elif action == "UPDATE_GAME":
                # 接收新檔案並覆蓋舊檔案
                send_json(conn, {"status": "READY"})
                zip_name = request['filename']
                zip_path = os.path.join(current_dir, "uploaded_game", zip_name)
                
                with open(zip_path, "wb") as f:
                    received = 0
                    while received < request['size']:
                        chunk = recv_frame(conn)
                        if not chunk: break
                        f.write(chunk)
                        received += len(chunk)
                
                # 自動解壓覆蓋 (確保玩家玩到的是新版)
                extract_path = zip_path.replace(".zip", "")
                if os.path.exists(extract_path):
                    shutil.rmtree(extract_path)
                with zipfile.ZipFile(zip_path, 'r') as z:
                    z.extractall(extract_path)

                # 更新資料庫
                from db_server import update_game_version_db
                update_game_version_db(request['game_name'], user_data['username'], request['version'], request['description'])
                response = {"status": "SUCCESS", "message": f"遊戲 {request['game_name']} 已更新至 v{request['version']}"}

            elif action == "DELETE_GAME":
                g_name = request['game_name']
                from db_server import delete_game_db
                if delete_game_db(g_name, user_data['username']):
                    # 同步清理實體檔案，避免下架後還能被搜到
                    zip_path = os.path.join(current_dir, "uploaded_game", f"{g_name}.zip")
                    folder_path = os.path.join(current_dir, "uploaded_game", g_name)
                    if os.path.exists(zip_path): os.remove(zip_path)
                    if os.path.exists(folder_path): shutil.rmtree(folder_path)
                    response = {"status": "SUCCESS", "message": "下架成功"}
                else:
                    response = {"status": "FAIL", "message": "下架失敗"}

            # 3. 回傳結果給 Client
            send_json(conn, response)

    except Exception as e:
        print(f"[異常] {addr} 發生錯誤: {e}")
    finally:
        print(f"[斷線] {addr} (使用者: {user_data['username'] if user_data else '未登入'})")
        conn.close()

def start_server():
    """
    Server 啟動主迴圈
    """
    required_dir = [os.path.join(current_dir, "uploaded_game")]
    for d in required_dir :
        if not os.path.exists(d) :
            print(f"[系統] 自動建立遺失的資料夾: {d}")
            os.makedirs(d)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # 允許 Port 重複使用 (避免重啟 Server 時報錯 "Address already in use")
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind((HOST, PORT))
        server.listen()
        print(f"[啟動] Server 正在監聽 {HOST}:{PORT}")
        print("[等待連線] 按 Ctrl+C 關閉 Server...")

        while True:
            # 接受新連線
            conn, addr = server.accept()
            
            # 為這個連線開一個新的 Thread 去處理，主程式繼續等待下一個人
            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.daemon = True # 設定為 Daemon，Server 關閉時 Thread 會自動跟著關
            thread.start()
            
            print(f"[線上人數] 目前連線數: {threading.active_count() - 1}")

    except KeyboardInterrupt:
        print("\n[關閉] Server 正在關閉...")
    finally:
        server.close()

if __name__ == "__main__":
    from db_server import init_db
    init_db()
    start_server()