import socket
import threading
import json
import sys
import os
import subprocess
import shutil
import zipfile
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# --- Import 自訂模組 ---
from common.protocol import send_json, recv_json, recv_frame, send_frame
from common.constant import SERVER_PORT, SERVER_IP
from db_server import register_user, login_check, add_game, get_db_connection, get_games_by_author, record_play, add_review, get_game_reviews

# --- Server 設定 ---
HOST = '0.0.0.0'  # 監聽所有網卡 (讓別人也能連進來)
PORT = SERVER_PORT

rooms = {}
room_id_counter = 100
rooms_lock = threading.Lock()
online_users = {}  # username -> conn
online_users_lock = threading.Lock()


def start_game_process(game_id, room_id):
    temp_sock = socket.socket()
    temp_sock.bind(('', 0))
    game_port = temp_sock.getsockname()[1]
    temp_sock.close()

    game_dir = os.path.join(current_dir, "uploaded_game", game_id)
    server_dir = os.path.join(game_dir, "server")
    server_script = os.path.join(server_dir, "game_server.py")

    cmd = [sys.executable, server_script, str(game_port), str(room_id)]

    subprocess.Popen(
        cmd, 
        cwd=server_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    time.sleep(1.0)
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
                if not user:
                    response = {"status": "FAIL", "message": "帳號或密碼錯誤"}
                else:
                    with online_users_lock:
                        if username in online_users:
                            response = {
                                "status": "FAIL",
                                "message": "此帳號已在其他地方登入"
                            }
                        else:
                            user_data = user
                            online_users[username] = conn
                            response = {
                                "status": "SUCCESS",
                                "message": "登入成功",
                                "user": {
                                    "username": user['username'],
                                    "role": user['role']
                                }
                            }


            elif action == "UPLOAD":
                if not user_data or user_data['role'] != 'developer':
                    send_json(conn, {"status": "FAIL", "message": "權限不足"})
                    continue

                game_name = request.get("game_name")
                version = request.get("version")
                desc = request.get("description")
                filename = request.get("filename")
                file_size = request.get("size")
                max_players = request.get("max_players", 2)

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

                    extract_path = zip_path.replace(".zip", "")
                    if os.path.exists(extract_path): shutil.rmtree(extract_path)
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        zf.extractall(extract_path)

                    client_dir = os.path.join(extract_path, "client")
                    player_zip = os.path.join(current_dir, "uploaded_game", f"{game_name}.zip")

                    if not os.path.isdir(client_dir):
                        raise Exception("上傳的遊戲缺少 client 資料夾")

                    shutil.make_archive(
                        player_zip.replace(".zip", ""),
                        "zip",
                        client_dir
                    )
                        
                    # 2. 寫入資料庫 (符合 PDF Step 6)
                    # 我們將 zip 檔名作為路徑存入
                    if add_game(game_name, version, desc, filename, user_data['username'], max_players):
                        response = {"status": "SUCCESS", "message": f"遊戲 {game_name} 上架成功"}
                    else:
                        response = {"status": "FAIL", "message": "資料庫寫入失敗"}
                except Exception as e:
                    response = {"status": "FAIL", "message": f"上傳中斷: {e}"}

            elif action == "LIST_MY_GAMES":
                # 取得該開發者的遊戲 (符合 PDF Step 7)
                my_games = get_games_by_author(user_data['username'])
                response = {"status": "SUCCESS", "games": my_games}

            elif action == "UPDATE_GAME":
                # 1. 接收新檔案並覆蓋舊檔案
                send_json(conn, {"status": "READY"})
                game_name = request['game_name'] # 確保有拿到 game_name
                zip_name = request['filename']
                zip_path = os.path.join(current_dir, "uploaded_game", zip_name)
                
                try:
                    with open(zip_path, "wb") as f:
                        received = 0
                        while received < request['size']:
                            chunk = recv_frame(conn)
                            if not chunk: break
                            f.write(chunk)
                            received += len(chunk)
                    
                    # 2. 自動解壓覆蓋
                    extract_path = zip_path.replace(".zip", "")
                    if os.path.exists(extract_path):
                        shutil.rmtree(extract_path)
                    with zipfile.ZipFile(zip_path, 'r') as z:
                        z.extractall(extract_path)

                    # --- 關鍵修正：重新產生玩家下載專用的 client-only zip ---
                    client_dir = os.path.join(extract_path, "client")
                    # 這是 DOWNLOAD action 會讀取的路徑: f"{game_id}.zip"
                    player_zip = os.path.join(current_dir, "uploaded_game", f"{game_name}.zip")

                    if not os.path.isdir(client_dir):
                        raise Exception("更新包中缺少 client 資料夾")

                    # 重新打包，確保結構與 UPLOAD 時一致
                    shutil.make_archive(
                        player_zip.replace(".zip", ""),
                        "zip",
                        client_dir
                    )
                    # ---------------------------------------------------

                    # 3. 更新資料庫
                    from db_server import update_game_version_db
                    update_game_version_db(game_name, user_data['username'], request['version'], request['description'], request.get('max_players', 2))
                    
                    response = {"status": "SUCCESS", "message": f"遊戲 {game_name} 已更新至 v{request['version']}"}
                    
                except Exception as e:
                    response = {"status": "FAIL", "message": f"更新失敗: {e}"}

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

            elif action == "LIST_GAMES":
                conn_db = get_db_connection()
                # 結合平均評分與評論數 (P1 要求)
                query = '''
                    SELECT g.*, AVG(r.rating) as avg_rating, COUNT(r.id) as review_count
                    FROM games g LEFT JOIN reviews r ON g.name = r.game_name
                    GROUP BY g.name
                '''
                games = [dict(row) for row in conn_db.execute(query).fetchall()]
                conn_db.close()
                response = {"status": "SUCCESS", "games": games}

            elif action == "DOWNLOAD":
                zip_path = os.path.join(current_dir, "uploaded_game", f"{request['game_id']}.zip")
                if os.path.exists(zip_path):
                    send_json(conn, {"status": "SUCCESS", "size": os.path.getsize(zip_path)})
                    with open(zip_path, "rb") as f:
                        while chunk := f.read(60000): send_frame(conn, chunk)
                    continue 
                else: response = {"status": "FAIL", "message": "檔案不存在"}

            # --- 4. 房間管理與遊玩紀錄 (RQU-5, 6) ---
            elif action == "CREATE_ROOM":
                global room_id_counter
                rid = str(room_id_counter)
                room_id_counter += 1
                gid = request['game_id']
                conn_db = get_db_connection()
                game_info = conn_db.execute("SELECT version, max_players FROM games WHERE name = ?", (gid,)).fetchone()
                conn_db.close()

                if not game_info:
                    response = {"status": "FAIL", "message": "找不到該遊戲資訊"}
                else:
                    cur_ver = game_info['version']
                    max_p = game_info['max_players']

                with rooms_lock:
                    rooms[rid] = {
                        "game_id": gid, 
                        "version": cur_ver, 
                        "players": [user_data['username']], 
                        "max_players": max_p, # 記錄此房間的人數上限
                        "status": "WAITING"
                    }
                response = {"status": "SUCCESS", "room_id": rid}

            elif action == "LIST_ROOMS":
                with rooms_lock:
                    r_list = [{"room_id": k, "game_id": v["game_id"], "player_count": len(v["players"]), "max_players":v["max_players"], "status": v["status"]} for k, v in rooms.items()]
                response = {"status": "SUCCESS", "rooms": r_list}

            elif action == "JOIN_ROOM":
                rid = request.get('room_id')
                with rooms_lock:
                    room = rooms.get(rid)
                    if not room or room['status'] != "WAITING":
                        response = {"status": "FAIL", "message": "房間無法加入"}
                    elif len(room['players']) >= room['max_players']:
                        response = {"status": "FAIL", "message": "房間已滿"}
                    else:
                        room['players'].append(user_data['username'])

                        # 檢查是否達到啟動條件
                        if len(room['players']) == room['max_players']:
                            room['status'] = "PLAYING"
                            g_port = start_game_process(room['game_id'], rid)
                            room['game_port'] = g_port
                            response = {"status": "SUCCESS", "game_start": True}
                        else:
                            response = {"status": "SUCCESS", "game_start": False}

            elif action == "CHECK_ROOM":
                rid = request.get('room_id')
                with rooms_lock:
                    room = rooms.get(rid)

                    if room and room.get("game_port"):
                        response = {
                            "status": "SUCCESS",
                            "game_start": True,
                            "game_id": room['game_id'],
                            "version": room.get('version'),
                            "game_ip": SERVER_IP,
                            "game_port": room['game_port']
                        }
                    else:
                        response = {
                            "status": "SUCCESS",
                            "game_start": False,
                            "players": room['players'] if room else [],
                            "max_players": room['max_players'] if room else 2
                        }

            # --- 5. 評價系統 (RQU-6) ---
            elif action == "SUBMIT_REVIEW":
                status, msg = add_review(request['game_name'], user_data['username'], request['rating'], request['comment'])
                response = {"status": "SUCCESS" if status else "FAIL", "message": msg}

            elif action == "GET_REVIEWS":
                response = {"status": "SUCCESS", "reviews": get_game_reviews(request['game_name'])}

            send_json(conn, response)

    except Exception as e:
        print(f"[異常] {addr} 發生錯誤: {e}")
    finally:
        if user_data:
            with online_users_lock:
                online_users.pop(user_data['username'], None)
        print(f"[斷線] {addr} (使用者: {user_data['username'] if user_data else '未登入'})")
        conn.close()

def handle_upload(conn, game_name):
    size = int.from_bytes(conn.recv(4), "big")
    data = conn.recv(size)

    game_dir = f"game_host/{game_name}"
    os.makedirs(game_dir, exist_ok=True)

    zip_path = os.path.join(game_dir, "game.zip")
    with open(zip_path, "wb") as f:
        f.write(data)

    print(f"[上架完成] {game_name}")

def handle_upload_connection(conn):
    line = conn.recv(64).decode()
    if line.startswith("UPLOAD"):
        _, game_name = line.split()
        handle_upload(conn, game_name)


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