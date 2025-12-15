import socket
import sys
from protocol import send_json, recv_json

def main():
    if len(sys.argv) < 3:
        print("Usage: python run.py <server_ip> <server_port>")
        return

    ip = sys.argv[1]
    port = int(sys.argv[2])

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ip, port))

    info = recv_json(sock)
    print(info["message"])

    while True:
        choice = input("請輸入 rock / paper / scissors: ").strip().lower()
        if choice in ("rock", "paper", "scissors"):
            break

    send_json(sock, {"choice": choice})

    result = recv_json(sock)
    print("\n=== 遊戲結果 ===")
    print(f"你出: {result['you']}")
    print(f"對手出: {result['opponent']}")

    if result["result"] == "DRAW":
        print("結果：平手")
    elif result["result"] == "P1":
        print("結果：你贏了 🎉")
    else:
        print("結果：你輸了 😢")

    sock.close()

if __name__ == "__main__":
    main()
