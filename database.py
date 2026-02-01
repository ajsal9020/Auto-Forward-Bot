import sqlite3
import os

class Database:
    def __init__(self, db_name="bot.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.setup()

    def setup(self):
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                             (user_id INTEGER PRIMARY KEY, name TEXT)''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS config 
                             (key TEXT PRIMARY KEY, value TEXT)''')
        self.conn.commit()

    def add_user(self, user_id, name):
        self.cursor.execute("INSERT OR REPLACE INTO users (user_id, name) VALUES (?, ?)", (user_id, name))
        self.conn.commit()

    def get_all_users(self):
        self.cursor.execute("SELECT user_id, name FROM users")
        return self.cursor.fetchall()

    def set_config(self, key, value):
        self.cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))
        self.conn.commit()

    def get_config(self, key):
        self.cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
        res = self.cursor.fetchone()
        return res[0] if res else None

db = Database()
