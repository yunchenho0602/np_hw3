import sqlite3
import os
import threading

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_store.db")
db_lock = threading.Lock()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row 
    return conn

def init_db():
    if os.path.exists(DB_PATH):
        print(f"[DB] 資料庫已存在: {DB_PATH}")
        return

    print(f"[DB] 建立新資料庫: {DB_PATH}")
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. 建立使用者資料表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'player'
            )
        ''')
        
        # 2. 建立遊戲資料表 (預先準備好，之後上架會用到)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS games (
                game_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                version TEXT NOT NULL,
                description TEXT,
                exe_path TEXT NOT NULL,
                author_username TEXT NOT NULL,
                FOREIGN KEY (author_username) REFERENCES users (username)
            )
        ''')
        
        conn.commit()
        conn.close()

def register_user(username, password, role='player'):

    with db_lock:
        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (username, password, role)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False 
        except Exception as e:
            print(f"[DB Error] Register: {e}")
            return False
        finally:
            conn.close()

def login_check(username, password):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE username = ? AND password = ?", 
            (username, password)
        )
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return dict(user)
        return None

if __name__ == "__main__":
    init_db()