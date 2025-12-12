import socket
import threading
import tkinter as tk
from tkinter import messagebox
import json
import sys
import queue
import time

# --- 嘗試匯入 protocol，解決路徑問題 ---
try:
    from protocol import send_json, recv_json
except ImportError:
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from protocol import send_json, recv_json

# --- 遊戲常數設定 ---
WIDTH = 10
HEIGHT = 20
CELL_SIZE = 30  # 稍微放大一點比較好玩

TETROMINOS = {
    'I': [(0,1),(1,1),(2,1),(3,1)],
    'O': [(1,0),(2,0),(1,1),(2,1)],
    'T': [(1,0),(0,1),(1,1),(2,1)],
    'S': [(1,0),(2,0),(0,1),(1,1)],
    'Z': [(0,0),(1,0),(1,1),(2,1)],
    'J': [(0,0),(0,1),(1,1),(2,1)],
    'L': [(2,0),(0,1),(1,1),(2,1)],
}

COLORS = {
    'I': '#00ffff', 'O': '#ffff00', 'T': '#aa00ff',
    'S': '#00ff00', 'Z': '#ff0000', 'J': '#0000ff',
    'L': '#ff8800', 'GRAY': '#333333', 'BLACK': '#000000'
}

# --- 網路客戶端類別 (只負責跟 GameServer 講話) ---
class GameClient:
    def __init__(self, ip, port, username, gui_queue):
        self.server_ip = ip
        self.server_port = port
        self.username = username
        self.gui_queue = gui_queue
        self.sock = None
        self.running = True

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # 嘗試連線，如果 Server 還沒啟動完畢，重試幾次
            for i in range(5):
                try:
                    self.sock.connect((self.server_ip, self.server_port))
                    break
                except ConnectionRefusedError:
                    print(f"連線失敗，重試中 ({i+1}/5)...")
                    time.sleep(1)
            
            # 發送握手包 (告訴 Server 我是誰)
            # 注意：這裡根據你的 game_server 邏輯，可能需要調整
            # 假設 Server 一連上就會自動將我們加入遊戲
            print(f"[網路] 已連線到 {self.server_ip}:{self.server_port}")
            
            # 啟動接收執行緒
            threading.Thread(target=self.receive_loop, daemon=True).start()
            return True
        except Exception as e:
            print(f"[網路錯誤] {e}")
            return False

    def send_action(self, action_type, payload=None):
        """傳送指令給 Server"""
        if not self.sock: return
        try:
            req = {"type": action_type, "user": self.username}
            if payload:
                req.update(payload)
            send_json(self.sock, req)
        except Exception as e:
            print(f"[傳送錯誤] {e}")

    def receive_loop(self):
        """背景接收 Server 傳來的遊戲狀態"""
        try:
            while self.running:
                data = recv_json(self.sock)
                if not data:
                    break
                # 將收到的資料丟進 Queue，讓主執行緒(GUI)處理
                self.gui_queue.put(data)
        except Exception as e:
            print(f"[斷線] {e}")
        finally:
            self.gui_queue.put({"type": "DISCONNECTED"})

# --- GUI 介面類別 (只負責畫圖) ---
class TetrisGUI:
    def __init__(self, username, ip, port):
        self.username = username
        self.target_ip = ip
        self.target_port = port
        
        # 1. 初始化視窗
        self.root = tk.Tk()
        self.root.title(f"Tetris Battle - {username}")
        self.root.geometry("800x650") # 寬度設寬一點，可以顯示對手
        
        # 2. 建立畫布與狀態列
        self.setup_ui()
        
        # 3. 初始化遊戲數據
        self.my_board = [[0]*WIDTH for _ in range(HEIGHT)]
        self.op_board = [[0]*WIDTH for _ in range(HEIGHT)] # 對手的畫面
        self.score = 0
        
        # 4. 啟動網路連線
        self.queue = queue.Queue()
        self.client = GameClient(ip, port, username, self.queue)
        
        # 5. 綁定按鍵
        self.root.bind("<Key>", self.on_key)
        
        # 6. 開始處理訊息迴圈
        if self.client.connect():
            self.status_label.config(text=f"已連線: {ip}:{port}", fg="green")
            self.root.after(100, self.process_queue)
            self.root.mainloop()
        else:
            messagebox.showerror("錯誤", "無法連線到遊戲伺服器")
            self.root.destroy()

    def setup_ui(self):
        # 頂部狀態列
        self.top_frame = tk.Frame(self.root, bg="#222", pady=5)
        self.top_frame.pack(fill="x")
        
        self.info_label = tk.Label(self.top_frame, text=f"Player: {self.username}", fg="white", bg="#222", font=("Arial", 14))
        self.info_label.pack(side="left", padx=10)
        
        self.score_label = tk.Label(self.top_frame, text="Score: 0", fg="yellow", bg="#222", font=("Arial", 14))
        self.score_label.pack(side="right", padx=10)

        # 中間遊戲區 (左邊自己，右邊對手)
        self.game_frame = tk.Frame(self.root, bg="black")
        self.game_frame.pack(fill="both", expand=True)
        
        # 自己的畫布
        self.canvas = tk.Canvas(self.game_frame, width=300, height=600, bg="black", highlightthickness=0)
        self.canvas.pack(side="left", padx=20, pady=20)
        
        # 對手的畫布 (小一點)
        self.op_canvas = tk.Canvas(self.game_frame, width=200, height=400, bg="#111", highlightthickness=0)
        self.op_canvas.pack(side="right", padx=20, pady=20)
        
        self.create_grid(self.canvas, 300, 600, CELL_SIZE)
        
        # 底部狀態
        self.status_label = tk.Label(self.root, text="正在連線...", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

    def create_grid(self, canvas, w, h, size):
        # 畫格線 (視覺輔助)
        pass 

    def process_queue(self):
        """處理來自 Server 的訊息"""
        try:
            while True:
                msg = self.queue.get_nowait()
                msg_type = msg.get("type")
                
                if msg_type == "SNAPSHOT":
                    # Server 傳來最新的畫面狀態
                    self.update_board(msg)
                
                elif msg_type == "GAME_OVER":
                    winner = msg.get("winner")
                    result = "你贏了！" if winner == self.username else "你輸了..."
                    messagebox.showinfo("遊戲結束", f"遊戲結束\n{result}")
                    self.root.quit()
                    return

                elif msg_type == "DISCONNECTED":
                    self.status_label.config(text="與伺服器斷線", fg="red")
                    return
                
        except queue.Empty:
            pass
        finally:
            self.root.after(50, self.process_queue)

    def update_board(self, data):
        """根據 Server 資料重畫畫面"""
        # 更新自己的分數與畫面
        # 注意：這裡要根據你 game_server 傳回來的資料結構調整
        # 假設結構是: {'my_board': [[...]], 'op_board': [[...]], 'score': 100}
        
        # 這裡做個簡單的範例，實際要看 game_server 怎麼傳
        if "board" in data:
            self.draw_cells(self.canvas, data["board"], CELL_SIZE)
        
        if "score" in data:
            self.score = data["score"]
            self.score_label.config(text=f"Score: {self.score}")

        # 如果有對手資料
        if "op_board" in data:
            # 簡單畫一下對手
            pass

    def draw_cells(self, canvas, board_data, cell_size):
        """繪製方塊"""
        canvas.delete("block") # 清除舊方塊 (保留背景)
        
        # board_data 應該是一個 20x10 的二維陣列
        # 0 代表空，字串 'I', 'T' 代表方塊顏色
        for r, row in enumerate(board_data):
            for c, val in enumerate(row):
                if val:
                    color = COLORS.get(val, 'white')
                    x1 = c * cell_size
                    y1 = r * cell_size
                    x2 = x1 + cell_size
                    y2 = y1 + cell_size
                    canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="black", tags="block")

    def on_key(self, event):
        """處理按鍵並傳給 Server"""
        key = event.keysym
        if key == 'Left':
            self.client.send_action("MOVE", {"dir": "left"})
        elif key == 'Right':
            self.client.send_action("MOVE", {"dir": "right"})
        elif key == 'Up':
            self.client.send_action("ROTATE")
        elif key == 'Down':
            self.client.send_action("MOVE", {"dir": "down"})
        elif key == 'space':
            self.client.send_action("DROP")

# --- 主程式入口 ---
if __name__ == "__main__":
    # 預設值 (方便除錯)
    my_username = "TestPlayer"
    target_ip = "127.0.0.1"
    target_port = 6000

    # 讀取系統參數 (HW3 規定)
    # python run.py [username] [ip] [port]
    if len(sys.argv) >= 4:
        my_username = sys.argv[1]
        target_ip = sys.argv[2]
        target_port = int(sys.argv[3])
    
    print(f"啟動 Tetris Client: {my_username} -> {target_ip}:{target_port}")
    
    app = TetrisGUI(my_username, target_ip, target_port)