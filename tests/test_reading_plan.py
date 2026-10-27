"""Tests for the authoritative shared reading plan."""

import json
import tempfile
import unittest
from pathlib import Path

from app.reading_plan import ReadingPlanError, load_reading_plan


class ReadingPlanTests(unittest.TestCase):
    def test_loads_all_supplied_days_and_preserves_readings(self) -> None:
        plan = load_reading_plan()

        self.assertEqual(plan.total_days, 231)
        self.assertEqual(plan.final_day, 231)
        self.assertEqual(plan.get_day(17).reading, "ዘፍጥረት 16-18")
        self.assertEqual(plan.get_day(60).reading, "ዘኍልቁ 14-15 & መዝሙረ ዳዊት 90")
        self.assertEqual(plan.get_day(231).ethiopian_date, "ግንቦት 21")
        self.assertEqual(plan.get_day(1).gregorian_date.isoformat(), "2026-10-11")
        self.assertEqual(plan.get_day(83).gregorian_date.isoformat(), "2027-01-01")
        self.assertEqual(plan.get_day(142).gregorian_date.isoformat(), "2027-03-01")
        self.assertEqual(plan.get_day(231).gregorian_date.isoformat(), "2027-05-29")

    def test_out_of_range_days_have_no_reading(self) -> None:
        plan = load_reading_plan()

        self.assertIsNone(plan.get_day(0))
        self.assertIsNone(plan.get_day(232))

    def test_rejects_missing_day(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(
                json.dumps(
                    {
                        "title": "fixture",
                        "final_day": 2,
                        "gregorian_start_date": "2026-10-11",
                        "gregorian_end_date": "2026-10-12",
                        "entries": [
                            [1, "date", "reading", "2026-10-11"],
                            [3, "date", "reading", "2026-10-12"],
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ReadingPlanError, "Expected day 2"):
                load_reading_plan(path)


if __name__ == "__main__":
    unittest.main()
