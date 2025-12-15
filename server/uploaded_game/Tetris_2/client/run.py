import pygame,sys,socket,threading
from protocol import send_json,recv_json
from constants import *
state=None

def net(sock):
    global state
    while True:
        state=recv_json(sock)

def draw(board,ox,screen):
    for y in range(GRID_H):
        for x in range(GRID_W):
            v=board[y][x]
            if v:
                pygame.draw.rect(
                    screen,COLORS[v],
                    (ox+x*BLOCK,y*BLOCK,BLOCK-1,BLOCK-1)
                )

def main(user,ip,port):
    global state
    sock=socket.socket()
    sock.connect((ip,int(port)))
    threading.Thread(target=net,args=(sock,),daemon=True).start()

    pygame.init()
    screen=pygame.display.set_mode((SCREEN_W,SCREEN_H))
    clock=pygame.time.Clock()

    while True:
        for e in pygame.event.get():
            if e.type==pygame.QUIT: sys.exit()
            if e.type==pygame.KEYDOWN:
                m=None
                if e.key==pygame.K_LEFT: m="LEFT"
                if e.key==pygame.K_RIGHT: m="RIGHT"
                if e.key==pygame.K_UP: m="ROTATE"
                if e.key==pygame.K_SPACE: m="DROP"
                if m: send_json(sock,{"cmd":"input","key":m})

        screen.fill((0,0,0))
        if state:
            draw(state["p1"]["grid"],0,screen)
            draw(state["p2"]["grid"],GRID_W*BLOCK+40,screen)

            if state.get("game_over"):
                print("Winner:",state["winner"])
                pygame.time.wait(3000)
                sys.exit()

        pygame.display.flip()
        clock.tick(60)

if __name__=="__main__":
    main(sys.argv[1],sys.argv[2],sys.argv[3])
