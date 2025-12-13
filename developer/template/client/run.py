import sys
from protocol import send_json, recv_json # 使用包內自帶的協定

def main():
    # 大廳啟動指令格式: python run.py [username] [server_ip] [game_port]
    if len(sys.argv) < 4:
        print("Usage: python run.py <username> <ip> <port>")
        sys.exit(1)

    username = sys.argv[1]
    server_ip = sys.argv[2]
    server_port = int(sys.argv[3])

    print(f"--- 遊戲已啟動 ---")
    print(f"玩家名稱: {username}")
    print(f"連線目標: {server_ip}:{server_port}")

    # TODO: 開發者在此建立 GUI 並連線至遊戲伺服器
    # 例如: client_socket.connect((server_ip, server_port))

if __name__ == "__main__":
    main()