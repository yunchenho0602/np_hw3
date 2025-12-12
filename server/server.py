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
from common.protocol import send_json, recv_json, recv_frame, send_frame
from common.constant import SERVER_PORT, SERVER_IP
from db_server import register_user, login_check, add_game, get_db_connection, get_games_by_author, record_play, add_review, get_game_reviews

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

    game_dir = os.path.join(current_dir, "uploaded_game", game_id)
    server_script = os.path.join(game_dir, "game_server.py")

    cmd = [sys.executable, server_script, str(game_port), str(room_id)]

    subprocess.Popen(cmd, cwd=game_dir)

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

                    extract_path = zip_path.replace(".zip", "")
                    if os.path.exists(extract_path): shutil.rmtree(extract_path)
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        zf.extractall(extract_path)
                        
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
                with rooms_lock:
                    rooms[rid] = {"game_id": request['game_id'], "players": [user_data['username']], "status": "WAITING"}
                response = {"status": "SUCCESS", "room_id": rid}

            elif action == "LIST_ROOMS":
                with rooms_lock:
                    r_list = [{"room_id": k, "game_id": v["game_id"], "player_count": len(v["players"]), "status": v["status"]} for k, v in rooms.items()]
                response = {"status": "SUCCESS", "rooms": r_list}

            elif action == "JOIN_ROOM":
                rid = request.get('room_id') # 確保這裡用的是 request
                with rooms_lock:
                    room = rooms.get(rid)
                    if room and room['status'] == "WAITING":
                        # 1. 加入玩家列表
                        room['players'].append(user_data['username'])
                        # 2. 授予評分資格 (RQU-6)
                        record_play(user_data['username'], room['game_id'])
                        
                        # 3. 啟動遊戲進程
                        g_port = start_game_process(room['game_id'], rid)
                        room['status'] = "PLAYING"
                        room['game_port'] = g_port
                        
                        # 4. ★ 關鍵：從資料庫抓取該遊戲的最新版本號 (RQU-5 P2)
                        conn_db = get_db_connection()
                        g_info = conn_db.execute("SELECT version FROM games WHERE name=?", (room['game_id'],)).fetchone()
                        conn_db.close()
                        
                        # 5. 回傳完整資訊給挑戰者，解決 KeyError
                        response = {
                            "status": "SUCCESS", 
                            "game_start": True, 
                            "game_id": room['game_id'], # 補上這個
                            "version": g_info['version'] if g_info else "1.0.0", # 補上這個
                            "game_ip": SERVER_IP, 
                            "game_port": g_port
                        }
                    else:
                        response = {"status": "FAIL", "message": "房間已滿、不存在或已在遊戲中"}

            elif action == "CHECK_ROOM":
                rid = request.get('room_id')
                with rooms_lock:
                    room = rooms.get(rid)
                    # 如果人數滿了且遊戲已啟動
                    if room and len(room['players']) >= 2:
                        # 抓取版本號
                        conn_db = get_db_connection()
                        g_info = conn_db.execute("SELECT version FROM games WHERE name=?", (room['game_id'],)).fetchone()
                        conn_db.close()

                        # 回傳完整資訊給房主，確保房主也能自動校驗版本
                        response = {
                            "status": "SUCCESS", 
                            "game_start": True, 
                            "game_id": room['game_id'],
                            "version": g_info['version'] if g_info else "1.0.0",
                            "game_ip": SERVER_IP, 
                            "game_port": room.get('game_port')
                        }
                    else:
                        response = {"status": "SUCCESS", "game_start": False, "players": room['players'] if room else []}
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