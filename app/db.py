import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "email_agent.db"


def get_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gmail_id TEXT UNIQUE,
        sender TEXT,
        subject TEXT,
        category TEXT,
        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS drafts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gmail_id TEXT,
        draft_id TEXT,
        status TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()
