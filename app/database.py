"""SQLite connection and idempotent schema initialization."""

import sqlite3
from contextlib import closing
from pathlib import Path

from app.cloudflare_core import normalize_display_name, normalize_signup_value


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
                    private_chat_id INTEGER,
                    display_name TEXT,
                    academic_year TEXT,
                    department TEXT,
                    reminders_enabled INTEGER NOT NULL DEFAULT 1
                        CHECK (reminders_enabled IN (0, 1)),
                    leaderboard_opt_in INTEGER NOT NULL DEFAULT 0
                        CHECK (leaderboard_opt_in IN (0, 1))
                )
                """
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
            if "private_chat_id" not in columns:
                connection.execute("ALTER TABLE users ADD COLUMN private_chat_id INTEGER")
            if "display_name" not in columns:
                connection.execute("ALTER TABLE users ADD COLUMN display_name TEXT")
            if "academic_year" not in columns:
                connection.execute("ALTER TABLE users ADD COLUMN academic_year TEXT")
            if "department" not in columns:
                connection.execute("ALTER TABLE users ADD COLUMN department TEXT")
            if "leaderboard_opt_in" not in columns:
                connection.execute(
                    "ALTER TABLE users ADD COLUMN leaderboard_opt_in INTEGER NOT NULL DEFAULT 0 "
                    "CHECK (leaderboard_opt_in IN (0, 1))"
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS reminder_deliveries (
                    reminder_date TEXT NOT NULL,
                    telegram_user_id INTEGER NOT NULL,
                    plan_day INTEGER NOT NULL CHECK (plan_day > 0),
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'sent', 'failed')),
                    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
                    next_attempt_at TEXT,
                    last_error TEXT,
                    sent_at TEXT,
                    PRIMARY KEY (reminder_date, telegram_user_id),
                    FOREIGN KEY (telegram_user_id)
                        REFERENCES users (telegram_user_id) ON DELETE CASCADE
                )
                """
            )


def register_user(
    database_path: str | Path,
    telegram_user_id: int,
    private_chat_id: int | None = None,
) -> bool:
    """Register once, refresh the private chat, and return whether it was new."""
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO users (telegram_user_id, private_chat_id) VALUES (?, ?)",
                (telegram_user_id, private_chat_id),
            )
            is_new_user = cursor.rowcount == 1
            if not is_new_user and private_chat_id is not None:
                connection.execute(
                    "UPDATE users SET private_chat_id = ? WHERE telegram_user_id = ?",
                    (private_chat_id, telegram_user_id),
                )
    return is_new_user


def user_is_registered(database_path: str | Path, telegram_user_id: int) -> bool:
    """Return whether the user completed signup by choosing a display name."""
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT 1 FROM users WHERE telegram_user_id = ? "
            "AND display_name IS NOT NULL AND trim(display_name) != '' "
            "AND academic_year IS NOT NULL AND trim(academic_year) != '' "
            "AND department IS NOT NULL AND trim(department) != ''",
            (telegram_user_id,),
        ).fetchone()
    return row is not None


def user_has_account(database_path: str | Path, telegram_user_id: int) -> bool:
    """Return whether /start has created an account, even if signup is pending."""
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT 1 FROM users WHERE telegram_user_id = ?", (telegram_user_id,)
        ).fetchone()
    return row is not None


def signup_stage(database_path: str | Path, telegram_user_id: int) -> str | None:
    """Return the next missing field, or ``complete`` when signup is finished."""
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT display_name, academic_year, department FROM users WHERE telegram_user_id = ?",
            (telegram_user_id,),
        ).fetchone()
    if row is None:
        return None
    for field, value in zip(("name", "year", "department"), row):
        if not value or not value.strip():
            return field
    return "complete"


def save_signup_field(
    database_path: str | Path, telegram_user_id: int, field: str, value: str
) -> bool:
    """Save one validated field only when it is the user's current signup step."""
    rules = {
        "name": ("display_name", 2, 64),
        "year": ("academic_year", 1, 24),
        "department": ("department", 2, 80),
    }
    if field not in rules or signup_stage(database_path, telegram_user_id) != field:
        return False
    column, minimum, maximum = rules[field]
    cleaned = normalize_signup_value(value, minimum, maximum)
    if cleaned is None:
        return False
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            cursor = connection.execute(
                f"UPDATE users SET {column} = ? WHERE telegram_user_id = ? AND {column} IS NULL",
                (cleaned, telegram_user_id),
            )
    return cursor.rowcount == 1


def display_name(database_path: str | Path, telegram_user_id: int) -> str | None:
    """Return the user's chosen display name, if one has been saved."""
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT display_name FROM users WHERE telegram_user_id = ?",
            (telegram_user_id,),
        ).fetchone()
    return row[0] if row and row[0] else None


def profile_details(database_path: str | Path, telegram_user_id: int) -> dict[str, str] | None:
    """Read the caller's profile fields without returning other users' data."""
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT display_name, academic_year, department FROM users "
            "WHERE telegram_user_id = ?",
            (telegram_user_id,),
        ).fetchone()
    if row is None:
        return None
    return {"name": row[0] or "", "year": row[1] or "", "department": row[2] or ""}


def save_display_name(
    database_path: str | Path, telegram_user_id: int, name: str
) -> bool:
    """Save a validated name for an account created through /start."""
    cleaned = normalize_display_name(name)
    if cleaned is None:
        return False
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            cursor = connection.execute(
                "UPDATE users SET display_name = ? WHERE telegram_user_id = ?",
                (cleaned, telegram_user_id),
            )
    return cursor.rowcount == 1


def update_profile_field(
    database_path: str | Path, telegram_user_id: int, field: str, value: str
) -> bool:
    """Update one existing user's profile field after validating its length."""
    rules = {
        "name": ("display_name", 2, 64),
        "year": ("academic_year", 1, 24),
        "department": ("department", 2, 80),
    }
    if field not in rules:
        return False
    column, minimum, maximum = rules[field]
    cleaned = normalize_signup_value(value, minimum, maximum)
    if cleaned is None:
        return False
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            cursor = connection.execute(
                f"UPDATE users SET {column} = ? WHERE telegram_user_id = ?",
                (cleaned, telegram_user_id),
            )
    return cursor.rowcount == 1


def delete_user(database_path: str | Path, telegram_user_id: int) -> bool:
    """Delete one user's account and personal records; return whether it existed."""
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                "DELETE FROM reading_completions WHERE telegram_user_id = ?",
                (telegram_user_id,),
            )
            connection.execute(
                "DELETE FROM reminder_deliveries WHERE telegram_user_id = ?",
                (telegram_user_id,),
            )
            cursor = connection.execute(
                "DELETE FROM users WHERE telegram_user_id = ?",
                (telegram_user_id,),
            )
    return cursor.rowcount == 1


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


def set_leaderboard_opt_in(
    database_path: str | Path, telegram_user_id: int, enabled: bool
) -> None:
    """Set the user's explicit consent to appear on the private-chat leaderboard."""
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            connection.execute(
                "UPDATE users SET leaderboard_opt_in = ? WHERE telegram_user_id = ?",
                (int(enabled), telegram_user_id),
            )


def leaderboard_opt_in(database_path: str | Path, telegram_user_id: int) -> bool:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT leaderboard_opt_in FROM users WHERE telegram_user_id = ?",
            (telegram_user_id,),
        ).fetchone()
    return bool(row[0]) if row else False


def leaderboard_entries(
    database_path: str | Path, limit: int = 10
) -> tuple[tuple[int, str, str, int], ...]:
    """Return opted-in readers only, ordered by completions and then chosen name."""
    if limit < 1:
        raise ValueError("limit must be positive")
    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            """SELECT u.telegram_user_id, u.display_name, u.academic_year,
                      COUNT(c.plan_day) AS total
               FROM users AS u
               LEFT JOIN reading_completions AS c
                 ON c.telegram_user_id = u.telegram_user_id
               WHERE u.leaderboard_opt_in = 1
                 AND u.display_name IS NOT NULL AND trim(u.display_name) != ''
                 AND u.academic_year IS NOT NULL AND trim(u.academic_year) != ''
                 AND u.department IS NOT NULL AND trim(u.department) != ''
               GROUP BY u.telegram_user_id, u.display_name, u.academic_year
               ORDER BY total DESC, u.display_name COLLATE NOCASE, u.telegram_user_id
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return tuple((int(row[0]), str(row[1]), str(row[2]), int(row[3])) for row in rows)


def prepare_reminder_deliveries(database_path: str | Path, reminder_date: str, plan_day: int) -> None:
    """Create a unique pending delivery for each opted-in private-chat user."""
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            connection.execute(
                """INSERT OR IGNORE INTO reminder_deliveries
                   (reminder_date, telegram_user_id, plan_day)
                   SELECT ?, telegram_user_id, ? FROM users
                   WHERE reminders_enabled = 1 AND private_chat_id IS NOT NULL
                     AND display_name IS NOT NULL AND trim(display_name) != ''
                     AND academic_year IS NOT NULL AND trim(academic_year) != ''
                     AND department IS NOT NULL AND trim(department) != ''""",
                (reminder_date, plan_day),
            )


def due_reminder_deliveries(
    database_path: str | Path, reminder_date: str, now: str, max_attempts: int
) -> tuple[tuple[int, int, int], ...]:
    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            """SELECT d.telegram_user_id, u.private_chat_id, d.attempts
               FROM reminder_deliveries AS d
               JOIN users AS u ON u.telegram_user_id = d.telegram_user_id
               WHERE d.reminder_date = ? AND d.status != 'sent' AND d.attempts < ?
                 AND (d.next_attempt_at IS NULL OR d.next_attempt_at <= ?)
                 AND u.reminders_enabled = 1 AND u.private_chat_id IS NOT NULL
                 AND u.display_name IS NOT NULL AND trim(u.display_name) != ''
                 AND u.academic_year IS NOT NULL AND trim(u.academic_year) != ''
                 AND u.department IS NOT NULL AND trim(u.department) != ''
               ORDER BY d.telegram_user_id""",
            (reminder_date, max_attempts, now),
        ).fetchall()
    return tuple((row[0], row[1], row[2]) for row in rows)


def record_reminder_attempt(database_path: str | Path, reminder_date: str, user_id: int) -> None:
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            connection.execute(
                """UPDATE reminder_deliveries SET attempts = attempts + 1
                   WHERE reminder_date = ? AND telegram_user_id = ? AND status != 'sent'""",
                (reminder_date, user_id),
            )


def mark_reminder_sent(database_path: str | Path, reminder_date: str, user_id: int) -> None:
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            connection.execute(
                """UPDATE reminder_deliveries SET status = 'sent', sent_at = CURRENT_TIMESTAMP,
                   next_attempt_at = NULL, last_error = NULL
                   WHERE reminder_date = ? AND telegram_user_id = ?""",
                (reminder_date, user_id),
            )


def mark_reminder_failed(
    database_path: str | Path,
    reminder_date: str,
    user_id: int,
    error: str,
    next_attempt_at: str | None,
) -> None:
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            connection.execute(
                """UPDATE reminder_deliveries SET status = 'failed', last_error = ?,
                   next_attempt_at = ? WHERE reminder_date = ? AND telegram_user_id = ?""",
                (error[:500], next_attempt_at, reminder_date, user_id),
            )
