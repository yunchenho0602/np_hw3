import sys
import socket
import threading
import tkinter as tk
import time
from protocol import send_json, recv_json # 使用包內自帶的協定

# --- 遊戲常數 (從 player.py 移入) ---
WIDTH = 10
HEIGHT = 20
CELL = 24

class TetrisGUI:
    def __init__(self, username, ip, port):
        self.username = username
        self.root = tk.Tk()
        self.root.title(f"俄羅斯方塊對戰 - {username}")
        
        # 建立畫布：寬度足以放下兩個盤面 (自己與對手)
        self.canvas = tk.Canvas(self.root, width=500, height=520, bg='#111111')
        self.canvas.pack(pady=20)
        
        # 初始化 Socket 並連線至遊戲伺服器
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # 增加一點重試機制，防止 game_server 還沒啟動完成
            connected = False
            for _ in range(5):
                try:
                    self.sock.connect((ip, int(port)))
                    connected = True
                    break
                except:
                    time.sleep(0.5)
            
            if not connected:
                print("[錯誤] 無法連線至遊戲伺服器")
                sys.exit(1)
                
            # 發送初始使用者資訊
            send_json(self.sock, {"user": username})
        except Exception as e:
            print(f"[錯誤] 連線異常: {e}")
            sys.exit(1)

        # 綁定按鍵
        self.root.bind("<Key>", self.handle_key)
        
        # 啟動背景監聽執行緒
        threading.Thread(target=self.listen_server, daemon=True).start()
        
        # 啟動 GUI 主迴圈
        self.root.mainloop()

    def handle_key(self, event):
        # 將按鍵轉換為指令發送給 game_server
        mapping = {
            "Left": "left", 
            "Right": "right", 
            "Down": "down", 
            "Up": "rotate",
            "w": "rotate", "a": "left", "s": "down", "d": "right"
        }
        if event.keysym in mapping:
            send_json(self.sock, {"type": "MOVE", "dir": mapping[event.keysym]})

    def listen_server(self):
        """監聽來自 game_server 的廣播訊息"""
        while True:
            try:
                msg = recv_json(self.sock)
                if not msg: 
                    print("[通知] 伺服器已關閉連線")
                    break
                
                if msg['type'] == 'SNAPSHOT':
                    self.draw_board(msg['data'])
                elif msg['type'] == 'START':
                    print("遊戲開始！")
            except (ConnectionResetError, ConnectionAbortedError):
                print("[錯誤] 與遊戲伺服器的連線已中斷")
                break
            except Exception as e:
                print(f"[異常] 接收資料錯誤: {e}")
                break

    def cell_color(self, v):
        """根據格子數值回傳顏色"""
        if not v: return '#222222'
        return '#00ffff' # 這裡可以根據 TetrisPiece 類型擴充顏色

    def draw_board(self, data):
        """[關鍵修正] 實作繪圖邏輯"""
        self.canvas.delete("all")
        
        # data 格式預期為: { "player1": {"board": [...], "score": 0}, "player2": {...} }
        for i, (user, state) in enumerate(data.items()):
            board = state.get('board', [])
            score = state.get('score', 0)
            
            # 設定每個盤面的起始 X 偏移 (自己左邊，對手右邊)
            offset_x = 30 + (i * 250)
            
            # 畫出玩家名稱與分數
            self.canvas.create_text(
                offset_x + 60, 10, 
                text=f"{user}: {score}", fill='white', font=('Arial', 12, 'bold')
            )

            # 遍歷盤面陣列並畫出格子
            for r in range(HEIGHT):
                for c in range(WIDTH):
                    val = board[r][c]
                    color = self.cell_color(val)
                    x1 = offset_x + c * (CELL - 2)
                    y1 = 30 + r * (CELL - 2)
                    x2 = x1 + (CELL - 4)
                    y2 = y1 + (CELL - 4)
                    
                    self.canvas.create_rectangle(
                        x1, y1, x2, y2, 
                        fill=color, outline='#333333'
                    )

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

    # 實例化 GUI 並啟動
    TetrisGUI(username, server_ip, server_port)

if __name__ == "__main__":
    main()