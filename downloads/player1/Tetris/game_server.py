import sys
import socket
import threading
import json
import time
import random
from protocol import send_json, recv_json

# --- 遊戲設定與常數 ---
WIDTH = 10
HEIGHT = 20
MATCH_DURATION = 300  # 5分鐘
TETROMINOS = {
    'I': [(0,1),(1,1),(2,1),(3,1)], 'O': [(1,0),(2,0),(1,1),(2,1)],
    'T': [(1,0),(0,1),(1,1),(2,1)], 'S': [(1,0),(2,0),(0,1),(1,1)],
    'Z': [(0,0),(1,0),(1,1),(2,1)], 'J': [(0,0),(0,1),(1,1),(2,1)],
    'L': [(2,0),(0,1),(1,1),(2,1)],
}

# --- 全域狀態管理 ---
clients = []
clients_lock = threading.Lock()
game_started = False
match_start_time = None
current_room_id = "None"

def log(*args):
    print(f"[遊戲伺服器 RM:{current_room_id}]", *args)

# --- 核心類別 (維持原本邏輯) ---
class TetrisState:
    def __init__(self, seed_seq):
        self.board = [[0]*WIDTH for _ in range(HEIGHT)]
        self.seed_seq = seed_seq
        self.score = 0
        self.is_lost = False
        self.current_piece = self._new_piece()
    
    def _new_piece(self):
        shape = self.seed_seq.next_piece()
        return {'shape': shape, 'cells': list(TETROMINOS[shape]), 'x': 3, 'y': 0}

    def get_snapshot(self):
        # 建立包含當前方塊的暫時盤面
        temp_board = [row[:] for row in self.board]
        if self.current_piece:
            for dx, dy in self.current_piece['cells']:
                tx, ty = self.current_piece['x'] + dx, self.current_piece['y'] + dy
                if 0 <= tx < WIDTH and 0 <= ty < HEIGHT:
                    temp_board[ty][tx] = 1
        return {"board": temp_board, "score": self.score, "is_lost": self.is_lost}

    def move(self, dx, dy):
        if self.is_lost: return False
        if self._valid(self.current_piece['cells'], self.current_piece['x']+dx, self.current_piece['y']+dy):
            self.current_piece['x'] += dx
            self.current_piece['y'] += dy
            return True
        elif dy > 0: # 落地
            self._place()
            return False
        return False

    def rotate(self):
        new_cells = [(3-y, x) for (x,y) in self.current_piece['cells']]
        if self._valid(new_cells, self.current_piece['x'], self.current_piece['y']):
            self.current_piece['cells'] = new_cells

    def _valid(self, cells, x, y):
        for dx, dy in cells:
            tx, ty = x + dx, y + dy
            if tx < 0 or tx >= WIDTH or ty < 0 or ty >= HEIGHT or (ty >= 0 and self.board[ty][tx]):
                return False
        return True

    def _place(self):
        for dx, dy in self.current_piece['cells']:
            self.board[self.current_piece['y']+dy][self.current_piece['x']+dx] = 1
        # 消行邏輯
        new_board = [row for row in self.board if not all(row)]
        cleared = HEIGHT - len(new_board)
        self.score += cleared * 100
        while len(new_board) < HEIGHT: new_board.insert(0, [0]*WIDTH)
        self.board = new_board
        self.current_piece = self._new_piece()
        if not self._valid(self.current_piece['cells'], self.current_piece['x'], self.current_piece['y']):
            self.is_lost = True

class SeedSequence:
    def __init__(self, seed):
        self.rnd = random.Random(seed)
        self.seq = []
        self.idx = 0
    def next_piece(self):
        if self.idx >= len(self.seq):
            self.seq.extend(self.rnd.sample(list(TETROMINOS.keys()), 7))
        p = self.seq[self.idx]
        self.idx += 1
        return p

# --- 輔助函式 ---
def broadcast(msg):
    with clients_lock:
        for c in clients:
            try: send_json(c['conn'], msg)
            except: pass

def handle_player(conn, addr):
    global game_started, match_start_time
    try:
        # 使用 try-except 保護，避免單一玩家連線錯誤搞垮整個 Server
        init_req = recv_json(conn)
        if not init_req: return
        user_name = init_req.get('user', 'Player')
        
        # 確保 seed_seq 已經存在 (由 start_game_server 初始化)
        state = TetrisState(seed_seq) 
        
        with clients_lock:
            clients.append({'conn': conn, 'user': user_name, 'state': state})
            if len(clients) == 2:
                game_started = True
                match_start_time = time.time()
                broadcast({'type': 'START'})
        
        # 進入指令監聽迴圈
        while True:
            cmd = recv_json(conn)
            if not cmd: break
            # ... 處理 MOVE 指令 ...
            
    except Exception as e:
        print(f"[遊戲崩潰] 玩家 {addr} 導致錯誤: {e}")
    finally:
        conn.close()

def start_game_server(port, room_id):
    global seed_seq, current_room_id
    current_room_id = room_id
    seed_seq = SeedSequence(int(room_id) if room_id.isdigit() else 42)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', int(port)))
    s.listen(2)
    log(f"已啟動於 Port: {port}, 房間 ID: {room_id}")

    # 啟動 Tick Thread (負責重力與發送畫面快照)
    def tick_thread():
        global game_started
        while True:
            if game_started:
                # 處理重力 (每 0.5 秒自動下降)
                with clients_lock:
                    for c in clients: c['state'].move(0, 1)
                    # 發送全體快照
                    snapshots = {c['user']: c['state'].get_snapshot() for c in clients}
                    broadcast({'type': 'SNAPSHOT', 'data': snapshots})
                    
                    # 檢查勝負或超時
                    if any(c['state'].is_lost for c in clients) or \
                       (match_start_time and time.time() - match_start_time >= MATCH_DURATION):
                        # 結算邏輯...
                        game_started = False
            time.sleep(0.5)

    threading.Thread(target=tick_thread, daemon=True).start()

    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_player, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
    # Server 啟動格式: python game_server.py [port] [room_id]
    start_game_server(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "None")