"""Tests for foundational database setup."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.database import (
    completed_days,
    completed_reading_records,
    delete_user,
    display_name,
    due_reminder_deliveries,
    initialize_database,
    leaderboard_entries,
    leaderboard_opt_in,
    mark_reminder_sent,
    mark_read,
    profile_details,
    prepare_reminder_deliveries,
    reminders_enabled,
    register_user,
    save_display_name,
    save_signup_field,
    set_leaderboard_opt_in,
    update_profile_field,
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
            self.assertTrue(
                {
                    "telegram_user_id", "created_at", "reminders_enabled", "display_name",
                    "academic_year", "department", "leaderboard_opt_in",
                } <= columns
            )

    def test_initialization_migrates_an_existing_users_table(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "old.sqlite3"
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(
                    "CREATE TABLE users (telegram_user_id INTEGER PRIMARY KEY, "
                    "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                    "private_chat_id INTEGER, reminders_enabled INTEGER NOT NULL DEFAULT 1)"
                )
            initialize_database(database_path)
            initialize_database(database_path)
            with closing(sqlite3.connect(database_path)) as connection:
                columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
            self.assertTrue({"display_name", "academic_year", "department"} <= columns)
            self.assertIn("leaderboard_opt_in", columns)

    def test_registration_completion_and_reminder_settings_are_per_user(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "daily.sqlite3"
            initialize_database(database_path)

            self.assertFalse(user_is_registered(database_path, 10))
            self.assertTrue(register_user(database_path, 10))
            self.assertFalse(user_is_registered(database_path, 10))
            self.assertTrue(save_display_name(database_path, 10, "  ባርኮ  ፍሬው "))
            self.assertEqual(display_name(database_path, 10), "ባርኮ ፍሬው")
            self.assertFalse(user_is_registered(database_path, 10))
            self.assertFalse(save_signup_field(database_path, 10, "department", "ECS"))
            self.assertTrue(save_signup_field(database_path, 10, "year", "2"))
            self.assertTrue(save_signup_field(database_path, 10, "department", "ECS"))
            self.assertTrue(user_is_registered(database_path, 10))
            self.assertTrue(update_profile_field(database_path, 10, "name", "  Updated Name  "))
            self.assertTrue(update_profile_field(database_path, 10, "year", "3rd year"))
            self.assertFalse(update_profile_field(database_path, 10, "department", "x"))
            self.assertFalse(update_profile_field(database_path, 10, "telegram_user_id", "99"))
            self.assertEqual(
                profile_details(database_path, 10),
                {"name": "Updated Name", "year": "3rd year", "department": "ECS"},
            )
            self.assertIsNone(profile_details(database_path, 99))
            self.assertFalse(register_user(database_path, 10))
            self.assertTrue(mark_read(database_path, 10, 17))
            self.assertFalse(mark_read(database_path, 10, 17))
            self.assertEqual(completed_days(database_path, 10), (17,))
            self.assertEqual(completed_days(database_path, 11), ())
            set_reminders_enabled(database_path, 10, False)
            self.assertFalse(reminders_enabled(database_path, 10))
            self.assertTrue(reminders_enabled(database_path, 11))

    def test_completion_records_keep_timestamp_and_canonical_day_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "daily-verse.sqlite3"
            initialize_database(database_path)
            register_user(database_path, 10)
            mark_read(database_path, 10, 12)
            mark_read(database_path, 10, 3)
            records = completed_reading_records(database_path, 10)
            self.assertEqual(tuple(day for day, _timestamp in records), (3, 12))
            self.assertTrue(all(timestamp for _day, timestamp in records))

    def test_delete_user_removes_only_their_account_and_personal_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "daily.sqlite3"
            initialize_database(database_path)
            register_user(database_path, 10, 1010)
            register_user(database_path, 11, 1011)
            save_display_name(database_path, 10, "First reader")
            save_display_name(database_path, 11, "Second reader")
            for user_id in (10, 11):
                save_signup_field(database_path, user_id, "year", "2")
                save_signup_field(database_path, user_id, "department", "ECS")
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
            save_display_name(database_path, 10, "Reader")
            save_signup_field(database_path, 10, "year", "2")
            save_signup_field(database_path, 10, "department", "ECS")
            register_user(database_path, 11)
            register_user(database_path, 12, private_chat_id=1012)
            register_user(database_path, 13, private_chat_id=1013)
            save_display_name(database_path, 13, "Opted out")
            save_signup_field(database_path, 13, "year", "2")
            save_signup_field(database_path, 13, "department", "ECS")
            set_reminders_enabled(database_path, 13, False)

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

    def test_leaderboard_is_explicit_opt_in_sorted_and_limited(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "daily.sqlite3"
            initialize_database(database_path)
            for user_id, name, count in ((10, "Zara", 2), (11, "Abel", 2), (12, "Hidden", 4)):
                register_user(database_path, user_id)
                save_display_name(database_path, user_id, name)
                save_signup_field(database_path, user_id, "year", "2")
                save_signup_field(database_path, user_id, "department", "ECS")
                for day in range(1, count + 1):
                    mark_read(database_path, user_id, day)
            self.assertFalse(leaderboard_opt_in(database_path, 10))
            set_leaderboard_opt_in(database_path, 10, True)
            set_leaderboard_opt_in(database_path, 11, True)
            self.assertEqual(
                leaderboard_entries(database_path),
                ((11, "Abel", "2", 2), (10, "Zara", "2", 2)),
            )
            self.assertEqual(
                leaderboard_entries(database_path, limit=1), ((11, "Abel", "2", 2),)
            )
            set_leaderboard_opt_in(database_path, 10, False)
            self.assertEqual(
                leaderboard_entries(database_path), ((11, "Abel", "2", 2),)
            )


if __name__ == "__main__":
    unittest.main()
