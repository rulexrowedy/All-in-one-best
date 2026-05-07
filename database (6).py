import sqlite3
import hashlib
from pathlib import Path
from cryptography.fernet import Fernet
import os
import threading

DB_PATH = Path(__file__).parent / 'users.db'
ENCRYPTION_KEY_FILE = Path(__file__).parent / '.encryption_key'

_local = threading.local()

def get_encryption_key():
    if ENCRYPTION_KEY_FILE.exists():
        with open(ENCRYPTION_KEY_FILE, 'rb') as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(ENCRYPTION_KEY_FILE, 'wb') as f:
            f.write(key)
        return key

ENCRYPTION_KEY = get_encryption_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

def get_connection():
    if not hasattr(_local, 'conn') or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA synchronous=NORMAL")
        _local.conn.execute("PRAGMA cache_size=100")
    return _local.conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            post_id TEXT,
            comment_prefix TEXT,
            delay INTEGER DEFAULT 30,
            cookies_encrypted TEXT,
            comments TEXT,
            automation_running INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def encrypt_cookies(cookies):
    if not cookies:
        return None
    return cipher_suite.encrypt(cookies.encode()).decode()

def decrypt_cookies(encrypted_cookies):
    if not encrypted_cookies:
        return ""
    try:
        return cipher_suite.decrypt(encrypted_cookies.encode()).decode()
    except:
        return ""

def create_user(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        password_hash = hash_password(password)
        cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                       (username, password_hash))
        user_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO user_configs (user_id, post_id, comment_prefix, delay, comments)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, '', '', 30, ''))
        conn.commit()
        return True, "Account created successfully!"
    except sqlite3.IntegrityError:
        return False, "Username already exists!"
    except Exception as e:
        return False, f"Error: {str(e)}"

def verify_user(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, password_hash FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    if user and user[1] == hash_password(password):
        return user[0]
    return None

def get_user_config(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT post_id, comment_prefix, delay, cookies_encrypted, comments, automation_running
        FROM user_configs WHERE user_id = ?
    ''', (user_id,))
    config = cursor.fetchone()
    if config:
        return {
            'post_id': config[0] or '',
            'comment_prefix': config[1] or '',
            'delay': config[2] or 30,
            'cookies': decrypt_cookies(config[3]),
            'comments': config[4] or '',
            'automation_running': config[5] or 0
        }
    return None

def update_user_config(user_id, post_id, comment_prefix, delay, cookies, comments):
    conn = get_connection()
    cursor = conn.cursor()
    encrypted_cookies = encrypt_cookies(cookies)
    cursor.execute('''
        UPDATE user_configs
        SET post_id = ?, comment_prefix = ?, delay = ?, cookies_encrypted = ?,
            comments = ?, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
    ''', (post_id, comment_prefix, delay, encrypted_cookies, comments, user_id))
    conn.commit()

def get_username(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT username FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    return user[0] if user else None

def set_automation_running(user_id, is_running):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE user_configs
        SET automation_running = ?, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
    ''', (1 if is_running else 0, user_id))
    conn.commit()

def get_automation_running(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT automation_running FROM user_configs WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return bool(result[0]) if result else False

init_db()
