"""Back up and reset CipherNet data whose required private keys no longer exist."""
from __future__ import annotations
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

DATABASE = Path.home() / "Library/Application Support/CipherNet/ciphernet.db"


def main() -> None:
    if not DATABASE.exists():
        raise SystemExit(f"Database not found: {DATABASE}")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = DATABASE.with_name(f"ciphernet-unrecoverable-backup-{stamp}.db")
    shutil.copy2(DATABASE, backup)
    with sqlite3.connect(DATABASE) as connection:
        connection.execute("DELETE FROM messages")
        connection.execute("DELETE FROM users")
    print(f"Backup created: {backup}")
    print("Removed unrecoverable demo users and encrypted message envelopes.")


if __name__ == "__main__":
    main()
