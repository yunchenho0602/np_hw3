import sys,socket,threading
from protocol import send_json,recv_json

pid = None
state = None

def net(sock):
    global pid,state
    while True:
        msg = recv_json(sock)
        if "pid" in msg:
            pid = msg["pid"]
            print("你的 pid:", pid)
        else:
            state = msg
            print("\n狀態更新:", state)

def main(ip, port):
    sock = socket.socket()
    sock.connect((ip,int(port)))
    threading.Thread(target=net,args=(sock,),daemon=True).start()

    while True:
        cmd = input("> ")
        send_json(sock, {"cmd": cmd})

if __name__=="__main__":
    main(sys.argv[1],sys.argv[2])
