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
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT DEFAULT "player")')
        cursor.execute('''CREATE TABLE IF NOT EXISTS games (
            game_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, 
            version TEXT, description TEXT, exe_path TEXT, author_username TEXT, max_players INTEGER DEFAULT 2)''')
        cursor.execute('CREATE TABLE IF NOT EXISTS reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, game_name TEXT, username TEXT, rating INTEGER, comment TEXT)')
        cursor.execute('CREATE TABLE IF NOT EXISTS play_history (username TEXT, game_name TEXT, PRIMARY KEY (username, game_name))')
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

def add_game(name, version, description, exe_path, author, max_players):
    """將上架的遊戲資訊存入資料庫 (符合 PDF Step 6)"""
    with db_lock:
        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO games (name, version, description, exe_path, author_username, max_players) VALUES (?, ?, ?, ?, ?, ?)",
                (name, version, description, exe_path, author, max_players)
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"[DB Error] Add Game: {e}")
            return False
        finally:
            conn.close()

def get_games_by_author(author):
    """取得特定開發者上架的遊戲列表 (符合 PDF Step 7)"""
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM games WHERE author_username = ?", (author,))
        games = cursor.fetchall()
        conn.close()
        return [dict(g) for g in games]

def update_game_version_db(name, author, new_version, new_desc, new_max_players):
    """RQU-4: 更新遊戲版本資訊"""
    with db_lock:
        conn = get_db_connection()
        try:
            # 明確指定欄位名稱，避免 game_id 造成數量不符
            conn.execute(
                "UPDATE games SET version = ?, description = ?, max_players = ? WHERE name = ? AND author_username = ?",
                (new_version, new_desc, new_max_players, name, author)
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"[DB Error] Update Game: {e}")
            return False
        finally:
            conn.close()

def delete_game_db(name, author):
    """RQU-4: 刪除遊戲記錄"""
    with db_lock:
        conn = get_db_connection()
        try:
            conn.execute(
                "DELETE FROM games WHERE name = ? AND author_username = ?",
                (name, author)
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"[DB Error] Delete Game: {e}")
            return False
        finally:
            conn.close()

def record_play(username, game_name):
    with db_lock:
        conn = get_db_connection()
        conn.execute("INSERT OR IGNORE INTO play_history (username, game_name) VALUES (?, ?)", (username, game_name))
        conn.commit()
        conn.close()

def add_review(game_name, username, rating, comment):
    with db_lock:
        conn = get_db_connection()
        played = conn.execute("SELECT 1 FROM play_history WHERE username=? AND game_name=?", (username, game_name)).fetchone()
        if not played: return False, "需遊玩過才能評分"
        conn.execute("INSERT INTO reviews (game_name, username, rating, comment) VALUES (?, ?, ?, ?)", (game_name, username, rating, comment))
        conn.commit()
        conn.close()
        return True, "評價成功"

def get_game_reviews(game_name):
    conn = get_db_connection()
    res = conn.execute("SELECT username, rating, comment FROM reviews WHERE game_name=?", (game_name,)).fetchall()
    conn.close()
    return [dict(r) for r in res]

if __name__ == "__main__":
    init_db()