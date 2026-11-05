"""Exercise Cloudflare leaderboard SQL and migration with local SQLite."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.cloudflare_core import LEADERBOARD_QUERY, format_leaderboard_message


ROOT = Path(__file__).resolve().parents[1]
LEADERBOARD_MIGRATION = (
    ROOT / "cloudflare" / "worker" / "migrations" / "0006_add_leaderboard_opt_in.sql"
)


class CloudflareLeaderboardDatabaseTests(unittest.TestCase):
    def test_migration_defaults_users_to_private_and_query_lists_only_opted_in(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "worker.sqlite3"
            with closing(sqlite3.connect(database_path)) as connection:
                with connection:
                    connection.executescript(
                        """
                        CREATE TABLE users (
                            telegram_user_id INTEGER PRIMARY KEY,
                            display_name TEXT,
                            academic_year TEXT,
                            department TEXT,
                            reminders_enabled INTEGER NOT NULL DEFAULT 1
                        );
                        CREATE TABLE reading_completions (
                            telegram_user_id INTEGER NOT NULL,
                            plan_day INTEGER NOT NULL,
                            PRIMARY KEY (telegram_user_id, plan_day)
                        );
                        """
                    )
                    connection.executescript(LEADERBOARD_MIGRATION.read_text(encoding="utf-8"))
                    connection.executemany(
                        "INSERT INTO users (telegram_user_id, display_name, academic_year, department) "
                        "VALUES (?, ?, ?, ?)",
                        [
                            (10, "Zara", "2nd", "Software"),
                            (11, "Abel", "4th", "ECS"),
                            (12, "Hidden", "3rd", "ECS"),
                        ],
                    )
                    opt_in = connection.execute(
                        "SELECT leaderboard_opt_in FROM users WHERE telegram_user_id = 10"
                    ).fetchone()[0]
                    connection.execute(
                        "UPDATE users SET leaderboard_opt_in = 1 WHERE telegram_user_id IN (10, 11)"
                    )
                    connection.executemany(
                        "INSERT INTO reading_completions (telegram_user_id, plan_day) VALUES (?, ?)",
                        [(10, 1), (10, 2), (11, 1), (11, 2), (12, 1), (12, 2), (12, 3)],
                    )
                    rows = connection.execute(LEADERBOARD_QUERY).fetchall()

        self.assertEqual(opt_in, 0)
        self.assertEqual(rows, [("Abel", "4th", 2), ("Zara", "2nd", 2)])
        formatted = format_leaderboard_message(tuple(
            {"display_name": name, "academic_year": year, "completed": count}
            for name, year, count in rows
        ))
        self.assertIn("01  Abel  ·  Year 4th  ·  2 readings", formatted)
        self.assertIn("02  Zara  ·  Year 2nd  ·  2 readings", formatted)
        self.assertNotIn("Hidden", formatted)


if __name__ == "__main__":
    unittest.main()
