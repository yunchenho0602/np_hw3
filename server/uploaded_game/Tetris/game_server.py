import socket,threading,time,sys,os
from game_logic import TetrisGame
from protocol import send_json, recv_json

current = os.path.dirname(os.path.abspath(__file__))

while True:
    parent = os.path.dirname(current)
    if parent == current:
        break
    if os.path.isdir(os.path.join(parent, "common")):
        sys.path.insert(0, parent)
        break
    current = parent
from common.protocol import send_json, recv_json

players=[]
games=[TetrisGame(),TetrisGame()]

def handle(conn,pid):
    while True:
        msg=recv_json(conn)
        if not msg: break
        if msg["cmd"]=="input":
            key=msg["key"]
            g=games[pid]
            opp=games[1-pid]

            if key=="LEFT" and g.valid(dx=-1): g.x-=1
            elif key=="RIGHT" and g.valid(dx=1): g.x+=1
            elif key=="ROTATE": g.rotate()
            elif key=="DROP":
                lines=g.tick()
                if lines>=2:
                    opp.add_garbage(lines-1)

def game_loop():
    while True:
        time.sleep(0.5)
        for i in (0,1):
            if not games[i].dead:
                lines=games[i].tick()
                if lines>=2:
                    games[1-i].add_garbage(lines-1)

        state={
            "cmd":"state",
            "p1":games[0].serialize(),
            "p2":games[1].serialize(),
        }

        if games[0].dead or games[1].dead:
            state["game_over"]=True
            state["winner"]=0 if games[1].dead else 1

        for p in players:
            send_json(p,state)

def main(port):
    s=socket.socket()
    s.bind(("0.0.0.0",int(port)))
    s.listen(2)

    for i in range(2):
        c,_=s.accept()
        players.append(c)
        threading.Thread(target=handle,args=(c,i),daemon=True).start()

    game_loop()

if __name__=="__main__":
    main(sys.argv[1])
