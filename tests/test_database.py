"""Tests for foundational database setup."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.database import initialize_database


class DatabaseInitializationTests(unittest.TestCase):
    def test_initialization_is_repeatable_and_creates_user_table(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "nested" / "daily.sqlite3"

            initialize_database(database_path)
            initialize_database(database_path)

            with closing(sqlite3.connect(database_path)) as connection:
                table = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'users'"
                ).fetchone()
                columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}

            self.assertEqual(table, ("users",))
            self.assertTrue({"telegram_user_id", "created_at", "reminders_enabled"} <= columns)


if __name__ == "__main__":
    unittest.main()
