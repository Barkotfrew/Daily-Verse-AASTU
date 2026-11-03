"""Tests for foundational database setup."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.database import (
    completed_days,
    delete_user,
    due_reminder_deliveries,
    initialize_database,
    mark_reminder_sent,
    mark_read,
    prepare_reminder_deliveries,
    reminders_enabled,
    register_user,
    set_reminders_enabled,
    user_is_registered,
)


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

    def test_registration_completion_and_reminder_settings_are_per_user(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "daily.sqlite3"
            initialize_database(database_path)

            self.assertFalse(user_is_registered(database_path, 10))
            self.assertTrue(register_user(database_path, 10))
            self.assertTrue(user_is_registered(database_path, 10))
            self.assertFalse(register_user(database_path, 10))
            self.assertTrue(mark_read(database_path, 10, 17))
            self.assertFalse(mark_read(database_path, 10, 17))
            self.assertEqual(completed_days(database_path, 10), (17,))
            self.assertEqual(completed_days(database_path, 11), ())

            set_reminders_enabled(database_path, 10, False)
            self.assertFalse(reminders_enabled(database_path, 10))
            self.assertTrue(reminders_enabled(database_path, 11))

    def test_delete_user_removes_only_their_account_and_personal_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "daily.sqlite3"
            initialize_database(database_path)
            register_user(database_path, 10, 1010)
            register_user(database_path, 11, 1011)
            mark_read(database_path, 10, 17)
            mark_read(database_path, 11, 18)
            set_reminders_enabled(database_path, 10, False)

            self.assertTrue(delete_user(database_path, 10))
            self.assertFalse(delete_user(database_path, 10))
            self.assertFalse(user_is_registered(database_path, 10))
            self.assertTrue(user_is_registered(database_path, 11))
            self.assertEqual(completed_days(database_path, 10), ())
            self.assertEqual(completed_days(database_path, 11), (18,))

    def test_reminder_delivery_records_are_unique_and_persist_sent_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "daily.sqlite3"
            initialize_database(database_path)
            register_user(database_path, 10, private_chat_id=1010)
            register_user(database_path, 11)
            set_reminders_enabled(database_path, 12, False)

            prepare_reminder_deliveries(database_path, "2026-10-11", 1)
            prepare_reminder_deliveries(database_path, "2026-10-11", 1)
            due = due_reminder_deliveries(
                database_path, "2026-10-11", "2026-10-11T04:00:00+00:00", 5
            )

            self.assertEqual(due, ((10, 1010, 0),))
            mark_reminder_sent(database_path, "2026-10-11", 10)
            self.assertEqual(
                due_reminder_deliveries(
                    database_path, "2026-10-11", "2026-10-11T04:00:30+00:00", 5
                ),
                (),
            )


if __name__ == "__main__":
    unittest.main()
