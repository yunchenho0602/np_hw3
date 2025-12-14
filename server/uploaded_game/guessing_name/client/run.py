# client/run.py
import sys
import socket
from protocol import send_json, recv_json

def main():
    if len(sys.argv) < 4:
        print("Usage: python run.py <username> <ip> <port>")
        sys.exit(1)

    username = sys.argv[1]
    server_ip = sys.argv[2]
    server_port = int(sys.argv[3])

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((server_ip, server_port))

    send_json(s, {"username": username})

    while True:
        data = recv_json(s)

        if data["type"] == "your_turn":
            g = int(input("請輸入猜測數字: "))
            send_json(s, {"guess": g})

        elif data["type"] == "hint":
            print("[提示]", data["msg"])

        elif data["type"] == "end":
            print(f"勝利者: {data['winner']}")
            print(f"答案是: {data['answer']}")
            break

if __name__ == "__main__":
    main()
