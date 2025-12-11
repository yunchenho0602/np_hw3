import socket
import threading
import json
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# --- Import 自訂模組 ---
from common.protocol import send_json, recv_json
from common.constant import SERVER_PORT
from db_server import register_user, login_check

# --- Server 設定 ---
HOST = '0.0.0.0'  # 監聽所有網卡 (讓別人也能連進來)
PORT = SERVER_PORT

def handle_client(conn, addr):
    """
    處理單一 Client 的所有請求 (執行緒函式)
    """
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
                response = {"status": "FAIL", "message": "功能尚未實作"}

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
    start_server()