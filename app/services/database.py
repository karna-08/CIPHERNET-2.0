"""SQLite persistence for public identities and encrypted message envelopes."""
from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from app.core.config import get_settings


def _database_path() -> str:
    url = get_settings().database_url
    if not url.startswith("sqlite:///"):
        raise ValueError("CipherNet currently supports SQLite database URLs only")
    path = str(Path(url.removeprefix("sqlite:///")).expanduser())
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def connection():
    conn = sqlite3.connect(_database_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def initialize_database() -> None:
    with connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT NOT NULL UNIQUE COLLATE NOCASE,
          password_hash TEXT NOT NULL,
          public_key TEXT NOT NULL,
          private_key_envelope TEXT
        );
        CREATE TABLE IF NOT EXISTS messages (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          sender_id INTEGER NOT NULL REFERENCES users(id),
          receiver_id INTEGER NOT NULL REFERENCES users(id),
          content TEXT NOT NULL,
          iv TEXT NOT NULL,
          encrypted_key TEXT NOT NULL,
          sender_encrypted_key TEXT,
          timestamp TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_messages_participants ON messages(sender_id, receiver_id, id);
        """)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(messages)")}
        if "sender_encrypted_key" not in columns:
            conn.execute("ALTER TABLE messages ADD COLUMN sender_encrypted_key TEXT")
        user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        if "private_key_envelope" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN private_key_envelope TEXT")


def create_message(sender_id: int, receiver_id: int, content: str, iv: str, encrypted_key: str, sender_encrypted_key: str,
                   timestamp: datetime | None = None) -> dict:
    created = (timestamp or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    with connection() as conn:
        cursor = conn.execute(
            "INSERT INTO messages (sender_id, receiver_id, content, iv, encrypted_key, sender_encrypted_key, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sender_id, receiver_id, content, iv, encrypted_key, sender_encrypted_key, created),
        )
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)
