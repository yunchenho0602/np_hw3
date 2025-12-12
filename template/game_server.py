import sys
import socket
import threading
from protocol import send_json, recv_json

def handle_player(conn, addr):
    print(f"[遊戲] 玩家連線: {addr}")
    # 處理遊戲邏輯...

def start_game_server(port, room_id):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('0.0.0.0', int(port)))
    s.listen(2)
    print(f"[遊戲伺服器] 已啟動於 Port: {port}, 房間 ID: {room_id}")
    
    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_player, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    # Server 啟動格式: python game_server.py [port] [room_id]
    if len(sys.argv) < 2:
        sys.exit(1)
    start_game_server(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "None")