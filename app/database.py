"""SQLite connection and idempotent schema initialization."""

import sqlite3
from pathlib import Path


def initialize_database(database_path: str | Path) -> None:
    """Create the initial user table; safe to call on every application start."""
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_user_id INTEGER PRIMARY KEY,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                reminders_enabled INTEGER NOT NULL DEFAULT 1
                    CHECK (reminders_enabled IN (0, 1))
            )
            """
        )
