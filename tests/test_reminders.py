"""Tests for scheduled reminder timing and idempotent sends."""

from datetime import date, datetime, time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from app.database import initialize_database, register_user, save_display_name
from app.reading_plan import ReadingEntry, ReadingPlan
from app.readings import EAT
from app.services.reminders import deliver_due_reminders, reminder_text


class ReminderDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_delivers_at_eat_seven_once_even_after_repeated_scheduler_checks(self) -> None:
        entry = ReadingEntry(1, "ጥቅምት 1", "ዘፍጥረት 1-3", date(2026, 10, 11))
        plan = ReadingPlan("Test plan", (entry,))
        now = datetime(2026, 10, 11, 7, 5, tzinfo=EAT)
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "daily.sqlite3"
            initialize_database(database_path)
            register_user(database_path, 22, private_chat_id=22)
            save_display_name(database_path, 22, "Reader")
            bot = AsyncMock()

            first = await deliver_due_reminders(bot, database_path, plan, now=now)
            second = await deliver_due_reminders(bot, database_path, plan, now=now)

            self.assertEqual(first, 1)
            self.assertEqual(second, 0)
            bot.send_message.assert_awaited_once()
            self.assertIn("ዘፍጥረት 1-3", bot.send_message.await_args.args[1])

    async def test_does_not_deliver_before_seven_or_outside_plan(self) -> None:
        entry = ReadingEntry(1, "ጥቅምት 1", "ዘፍጥረት 1-3", date(2026, 10, 11))
        plan = ReadingPlan("Test plan", (entry,))
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "daily.sqlite3"
            initialize_database(database_path)
            register_user(database_path, 22, private_chat_id=22)
            save_display_name(database_path, 22, "Reader")
            bot = AsyncMock()

            before_time = await deliver_due_reminders(
                bot, database_path, plan, now=datetime(2026, 10, 11, 6, 59, tzinfo=EAT)
            )
            outside_plan = await deliver_due_reminders(
                bot, database_path, plan, now=datetime(2026, 10, 12, 7, 0, tzinfo=EAT)
            )

            self.assertEqual((before_time, outside_plan), (0, 0))
            bot.send_message.assert_not_awaited()

    async def test_custom_test_time_can_be_set_to_eight_nineteen_eat(self) -> None:
        entry = ReadingEntry(1, "ጥቅምት 1", "ዘፍጥረት 1-3", date(2026, 10, 11))
        plan = ReadingPlan("Test plan", (entry,))
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "daily.sqlite3"
            initialize_database(database_path)
            register_user(database_path, 22, private_chat_id=22)
            save_display_name(database_path, 22, "Reader")
            bot = AsyncMock()

            early = await deliver_due_reminders(
                bot,
                database_path,
                plan,
                now=datetime(2026, 10, 11, 8, 18, tzinfo=EAT),
                reminder_time=time(8, 19),
            )
            at_trigger = await deliver_due_reminders(
                bot,
                database_path,
                plan,
                now=datetime(2026, 10, 11, 8, 19, tzinfo=EAT),
                reminder_time=time(8, 19),
            )

            self.assertEqual((early, at_trigger), (0, 1))
            bot.send_message.assert_awaited_once()

    def test_template_contains_only_fixed_plan_fields_and_approved_greeting(self) -> None:
        entry = ReadingEntry(1, "ጥቅምት 1", "ዘፍጥረት 1-3", date(2026, 10, 11))
        message = reminder_text(entry)
        self.assertIn("ሰላም ተወዳጆች", message)
        self.assertIn("ቀን 1", message)
        self.assertIn("2026-10-11", message)
        self.assertIn("ዘፍጥረት 1-3", message)


if __name__ == "__main__":
    unittest.main()
