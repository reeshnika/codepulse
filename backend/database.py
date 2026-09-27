"""
Database module for CodePulse
SQLite setup and table initialization
"""

import os
import sqlite3
import logging

logger = logging.getLogger(__name__)

# Default database path inside the project's data directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DEFAULT_DB_PATH = os.path.join(DATA_DIR, 'codepulse.db')


def get_db(db_path=None):
    """
    Returns an active sqlite3 database connection with Row factory enabled.
    """
    target_path = db_path or DEFAULT_DB_PATH
    dir_name = os.path.dirname(target_path)
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name, exist_ok=True)

    try:
        conn = sqlite3.connect(target_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logger.error(f"Failed to connect to database at {target_path}: {e}")
        raise


def init_db(db_path=None):
    """
    Initializes SQLite tables for sessions, keystrokes, flow_scores, and users.
    """
    target_path = db_path or DEFAULT_DB_PATH
    conn = get_db(target_path)
    cursor = conn.cursor()

    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE,
                user_id TEXT,
                start_time TEXT,
                end_time TEXT,
                duration REAL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS keystrokes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                key TEXT,
                press_time REAL,
                release_time REAL,
                flight_time REAL,
                dwell_time REAL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS flow_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                score REAL,
                state TEXT,
                speed REAL,
                accuracy REAL,
                focus REAL,
                clarity REAL,
                consistency REAL,
                timestamp TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE,
                fingerprint TEXT,
                created_at TEXT
            )
        ''')

        conn.commit()
        logger.info(f"Database initialized successfully at {target_path}")
    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"Error initializing database: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    init_db()
    print("Database tables initialized successfully!")
