# game_server.py
import socket
import threading
import json
import sys
import time
import random
import os  # 新增 os 用於強制結束

# --- 1. 修改 Import 方式 (確保能找到 protocol) ---
try:
    from protocol import recv_json, send_json
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from protocol import recv_json, send_json

HOST = '0.0.0.0'
WIDTH = 10
HEIGHT = 20

# --- 移除舊的大廳設定 ---
# LOBBY_HOST = '127.0.0.1' 
# LOBBY_PORT = 12001

TETROMINOS = {
    'I': [(0,1),(1,1),(2,1),(3,1)],
    'O': [(1,0),(2,0),(1,1),(2,1)],
    'T': [(1,0),(0,1),(1,1),(2,1)],
    'S': [(1,0),(2,0),(0,1),(1,1)],
    'Z': [(0,0),(1,0),(1,1),(2,1)],
    'J': [(0,0),(0,1),(1,1),(2,1)],
    'L': [(2,0),(0,1),(1,1),(2,1)],
}

MIN_PLAYERS = 2 

clients = []
clients_lock = threading.Lock()
game_started = False
match_start_time = None
MATCH_DURATION = 300  # 5 minutes limit

def log(*args):
    print(f"[GameServer {int(time.time())}]", *args)

def rotate_cells(cells, times=1):
    res = cells
    for _ in range(times%4):
        res = [ (3 - y, x) for (x,y) in res ]
    return res

class SeedSequence:
    def __init__(self, seed):
        self.seed = seed
        self.rnd = random.Random(seed)
        self.seq = []
        self.idx = 0
        self.lock = threading.Lock()
        self._ensure(20)

    def _ensure(self, n):
        while len(self.seq) < self.idx + n:
            keys = list(TETROMINOS.keys())
            bag = keys[:]
            self.rnd.shuffle(bag)
            self.seq.extend(bag)

    def get_piece(self):
        with self.lock:
            self._ensure(10)
            p = self.seq[self.idx]
            self.idx += 1
            return p

# Global seed generator
seed_gen = None

class TetrisState:
    def __init__(self):
        self.board = [[0]*WIDTH for _ in range(HEIGHT)]
        self.score = 0
        self.lines_cleared = 0
        self.piece = None
        self.held = None
        self.can_hold = True
        self.is_lost = False
        self.spawn_piece()

    def spawn_piece(self):
        shape = seed_gen.get_piece()
        self.piece = {
            'shape': shape,
            'rot': 0,
            'x': 3,
            'y': 0
        }
        if self.check_collision(self.piece):
            self.is_lost = True

    def check_collision(self, piece):
        shape = piece['shape']
        rot = piece['rot']
        px, py = piece['x'], piece['y']
        cells = rotate_cells(TETROMINOS[shape], rot)
        for cx, cy in cells:
            nx, ny = px + cx, py + cy
            if nx < 0 or nx >= WIDTH or ny >= HEIGHT:
                return True
            if ny >= 0 and self.board[ny][nx] != 0:
                return True
        return False

    def lock_piece(self):
        if not self.piece: return
        shape = self.piece['shape']
        rot = self.piece['rot']
        px, py = self.piece['x'], self.piece['y']
        cells = rotate_cells(TETROMINOS[shape], rot)
        for cx, cy in cells:
            nx, ny = px + cx, py + cy
            if 0 <= nx < WIDTH and 0 <= ny < HEIGHT:
                self.board[ny][nx] = shape
        
        self.clear_lines()
        self.spawn_piece()
        self.can_hold = True

    def clear_lines(self):
        new_board = [row for row in self.board if any(c == 0 for c in row)]
        cleared = HEIGHT - len(new_board)
        if cleared > 0:
            self.lines_cleared += cleared
            # simple scoring
            self.score += [0, 40, 100, 300, 1200][cleared] if cleared <= 4 else 1200
            for _ in range(cleared):
                new_board.insert(0, [0]*WIDTH)
            self.board = new_board

    def move(self, dx, dy):
        if self.is_lost or not self.piece: return False
        new_p = self.piece.copy()
        new_p['x'] += dx
        new_p['y'] += dy
        if not self.check_collision(new_p):
            self.piece = new_p
            return True
        return False

    def rotate(self):
        if self.is_lost or not self.piece: return
        new_p = self.piece.copy()
        new_p['rot'] = (new_p['rot'] + 1) % 4
        if not self.check_collision(new_p):
            self.piece = new_p
        else:
            # wall kick try
            if self.move(1, 0): 
                self.piece['rot'] = new_p['rot'] # simplistic kick
            elif self.move(-1, 0):
                self.piece['rot'] = new_p['rot']

    def drop(self):
        if self.is_lost or not self.piece: return
        while self.move(0, 1):
            pass
        self.lock_piece()

    def get_snapshot(self):
        return {
            'board': self.board,
            'score': self.score,
            'lines': self.lines_cleared,
            'piece': self.piece,
            'is_lost': self.is_lost
        }

def broadcast(msg):
    with clients_lock:
        to_remove = []
        for c in clients:
            try:
                send_json(c['conn'], msg)
            except:
                to_remove.append(c)
        for c in to_remove:
            clients.remove(c)

def compute_results_and_end(roomId, startAt):
    endAt = time.time()
    log('Game over. Computing results...')
    
    # Sort clients by score
    with clients_lock:
        sorted_clients = sorted(clients, key=lambda c: c['state'].score, reverse=True)
        
    scores = {}
    winner_username = None
    
    if sorted_clients:
        winner_username = sorted_clients[0]['user']
        for c in sorted_clients:
            scores[c['user']] = c['state'].score

    results = {
        'winner': winner_username,
        'scores': scores
    }
    
    # --- 2. 修改重點：移除連線回 Lobby 的程式碼 ---
    # 改成直接廣播結果並結束
    
    print(f"[GameServer] 遊戲結束，獲勝者: {winner_username}")
    
    # 廣播 GAME_OVER 給所有連線中的玩家 (讓 run.py 跳出視窗)
    broadcast({
        'type': 'GAME_OVER',
        'winner': winner_username,
        'scores': scores,
        'payload': results # 相容性保留
    })

    # 等待一秒確保封包送出
    time.sleep(1)
    
    # 強制結束程式 (釋放 Port 和資源)
    print("[GameServer] Shutting down...")
    os._exit(0)


def handle_client(conn, addr, roomId):
    user = f"Player_{addr[1]}" # default
    try:
        # 1. Login handshake
        req = recv_json(conn)
        if req.get('type') == 'LOGIN': # Support simplified LOGIN
            user = req.get('user', user)
        
        # 2. Init state
        state = TetrisState()
        with clients_lock:
            clients.append({'conn': conn, 'addr': addr, 'user': user, 'state': state})
            current_count = len(clients)
        
        log(f"Player {user} joined. Total: {current_count}/{MIN_PLAYERS}")
        
        if current_count >= MIN_PLAYERS:
            global game_started, match_start_time
            if not game_started:
                game_started = True
                match_start_time = time.time()
                log("Game Started!")
                broadcast({'type': 'START', 'timestamp': match_start_time})

        # 3. Command loop
        while True:
            msg = recv_json(conn)
            if not msg: break
            t = msg.get('type')
            
            if not game_started: continue
            if state.is_lost: continue

            if t == 'MOVE':
                d = msg.get('dir')
                if d == 'left': state.move(-1, 0)
                elif d == 'right': state.move(1, 0)
                elif d == 'down': state.move(0, 1)
            elif t == 'ROTATE':
                state.rotate()
            elif t == 'DROP':
                state.drop()
            
    except Exception as e:
        log(f"Client {user} error: {e}")
    finally:
        with clients_lock:
            # remove client logic if needed, or just mark offline
            pass
        try: conn.close()
        except: pass

def tick_thread(roomId):
    global game_started
    while True:
        if not game_started:
            time.sleep(0.1)
            continue
        
        # Game Loop
        try:
            start_t = time.time()
            # 1. Check game over conditions
            player_has_lost = False
            with clients_lock:
                for c in clients:
                    if c['state'].is_lost:
                        player_has_lost = True
                        break
            
            if player_has_lost:
                compute_results_and_end(roomId, match_start_time)
                # compute_results_and_end 會直接 exit，所以下面不會執行到
                break 

            if match_start_time and (time.time() - match_start_time) >= MATCH_DURATION:
                compute_results_and_end(roomId, match_start_time)
                break

            # 2. Apply gravity & Snapshot
            snapshots = {}
            with clients_lock:
                for i, c in enumerate(clients):
                    # gravity (simple: every tick moves down? maybe too fast. Let's make it simple)
                    # For a smoother game, gravity should be time-based. 
                    # Here we just check "can we move down?" periodically.
                    # To make it playable, maybe move down every 2 ticks or use a timer.
                    # For simplicity, let's just create snapshot here. Gravity is handled inside state if needed, 
                    # but usually state.move(0,1) is called by a separate timer or here.
                    
                    # 簡易重力：每 0.5 秒掉一格 (大約每兩次 tick)
                    if int(time.time() * 2) > int((time.time() - 0.25) * 2):
                        c['state'].move(0, 1)

                    snapshots[c['user']] = c['state'].get_snapshot()

            # 3. Send combined state to all
            # We need to send EVERYONE'S board to EVERYONE (for battle view)
            # data structure: { 'userA': {board...}, 'userB': {board...} }
            
            # 為了配合 run.py 的簡單接收，我們發送比較簡單的格式
            # 但如果要對戰，應該要包含對手資料
            
            with clients_lock:
                for c in clients:
                    # 準備給這個玩家的資料
                    my_data = snapshots.get(c['user'])
                    # 找對手資料 (假設只有兩個玩家)
                    op_data = None
                    for other_user, other_snap in snapshots.items():
                        if other_user != c['user']:
                            op_data = other_snap
                            break # 只取第一個對手
                    
                    payload = {
                        'type': 'SNAPSHOT',
                        'board': my_data['board'],
                        'score': my_data['score'],
                        'lines': my_data['lines'],
                        'piece': my_data['piece'],
                        'is_lost': my_data['is_lost']
                    }
                    if op_data:
                        payload['op_board'] = op_data['board']
                        payload['op_score'] = op_data['score']

                    try:
                        send_json(c['conn'], payload)
                    except:
                        pass

        except Exception as e:
            log('tick exception', e)
        
        time.sleep(0.1) # 10 FPS update rate

def run_game_server(port, roomId):
    global seed_gen
    seed_gen = SeedSequence(time.time())
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, int(port)))
    s.listen(4)
    log(f"Game Server started on port {port} (Room {roomId})")

    threading.Thread(target=tick_thread, args=(roomId,), daemon=True).start()

    try:
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr, roomId), daemon=True).start()
    except KeyboardInterrupt:
        pass
    finally:
        s.close()

if __name__ == '__main__':
    # 接收參數: python3 game_server.py <port> [roomId]
    if len(sys.argv) < 2:
        print('usage: python3 game_server.py <port> [roomId]')
        sys.exit(1)
        
    port = sys.argv[1]
    room_id = sys.argv[2] if len(sys.argv) > 2 else "TestRoom"
    
    run_game_server(port, room_id)