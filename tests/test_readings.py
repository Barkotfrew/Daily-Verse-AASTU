"""Tests for shared schedule lookup and Telegram display formatting."""

from datetime import date
import unittest

from app.reading_plan import load_reading_plan
from app.readings import entry_for_date, format_reading_entry


class ReadingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = load_reading_plan()

    def test_all_users_share_date_to_plan_day_mapping(self) -> None:
        entry = entry_for_date(self.plan, date(2026, 10, 27))

        self.assertEqual(entry.day, 17)
        self.assertEqual(entry.reading, "ዘፍጥረት 16-18")

    def test_date_outside_schedule_returns_no_entry(self) -> None:
        self.assertIsNone(entry_for_date(self.plan, date(2027, 5, 30)))

    def test_display_has_day_both_dates_and_reading(self) -> None:
        entry = self.plan.get_day(17)
        text = format_reading_entry(entry)

        self.assertIn("Day 17", text)
        self.assertIn("ጥቅምት 17", text)
        self.assertIn("2026-10-27", text)
        self.assertIn("ዘፍጥረት 16-18", text)


if __name__ == "__main__":
    unittest.main()
