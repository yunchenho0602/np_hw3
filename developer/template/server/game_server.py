import socket,threading,sys,time
from protocol import send_json,recv_json

players = {}   # pid -> socket
states = {}    # pid -> player state
lock = threading.Lock()
next_pid = 0

def handle(conn, pid):
    global states
    while True:
        msg = recv_json(conn)
        if not msg:
            break
        with lock:
            states[pid] = msg

    with lock:
        del players[pid]
        del states[pid]

def game_loop():
    while True:
        time.sleep(0.3)
        with lock:
            snapshot = {
                "players": states
            }
            for p in players.values():
                send_json(p, snapshot)

def main(port):
    global next_pid
    s = socket.socket()
    s.bind(("0.0.0.0", int(port)))
    s.listen()

    threading.Thread(target=game_loop,daemon=True).start()

    while True:
        c,_ = s.accept()
        pid = next_pid
        next_pid += 1

        players[pid] = c
        states[pid] = {}

        send_json(c, {"pid": pid})
        threading.Thread(target=handle,args=(c,pid),daemon=True).start()

if __name__=="__main__":
    main(sys.argv[1])
