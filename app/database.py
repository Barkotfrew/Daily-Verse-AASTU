"""SQLite connection and idempotent schema initialization."""

import sqlite3
from contextlib import closing
from pathlib import Path


def initialize_database(database_path: str | Path) -> None:
    """Create user and per-user completion tables; safe to repeat."""
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection:
        with connection:
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS reading_completions (
                    telegram_user_id INTEGER NOT NULL,
                    plan_day INTEGER NOT NULL CHECK (plan_day > 0),
                    completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (telegram_user_id, plan_day),
                    FOREIGN KEY (telegram_user_id)
                        REFERENCES users (telegram_user_id) ON DELETE CASCADE
                )
                """
            )


def register_user(database_path: str | Path, telegram_user_id: int) -> None:
    """Create a user once without resetting existing preferences or progress."""
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            connection.execute(
                "INSERT OR IGNORE INTO users (telegram_user_id) VALUES (?)",
                (telegram_user_id,),
            )


def set_reminders_enabled(
    database_path: str | Path, telegram_user_id: int, enabled: bool
) -> None:
    """Persist one user's reminder preference."""
    register_user(database_path, telegram_user_id)
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            connection.execute(
                "UPDATE users SET reminders_enabled = ? WHERE telegram_user_id = ?",
                (int(enabled), telegram_user_id),
            )


def reminders_enabled(database_path: str | Path, telegram_user_id: int) -> bool:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT reminders_enabled FROM users WHERE telegram_user_id = ?",
            (telegram_user_id,),
        ).fetchone()
    return bool(row[0]) if row else True


def mark_read(database_path: str | Path, telegram_user_id: int, plan_day: int) -> bool:
    """Mark a scheduled day complete; return False when it was already complete."""
    register_user(database_path, telegram_user_id)
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO reading_completions (telegram_user_id, plan_day)
                VALUES (?, ?)
                """,
                (telegram_user_id, plan_day),
            )
    return cursor.rowcount == 1


def completed_days(database_path: str | Path, telegram_user_id: int) -> tuple[int, ...]:
    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            """
            SELECT plan_day FROM reading_completions
            WHERE telegram_user_id = ? ORDER BY plan_day
            """,
            (telegram_user_id,),
        ).fetchall()
    return tuple(row[0] for row in rows)
