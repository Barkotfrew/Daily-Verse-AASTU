"""Tests for exporting the canonical plan into D1 seed SQL."""

import tempfile
import unittest
import sqlite3
from pathlib import Path

from scripts.export_d1_reading_plan import SOURCE, export_plan


class D1PlanExportTests(unittest.TestCase):
    def test_export_contains_all_231_authoritative_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "plan.sql"
            count = export_plan(SOURCE, output)
            sql = output.read_text(encoding="utf-8")
            database = sqlite3.connect(":memory:")
            schema = Path(__file__).resolve().parents[1] / "cloudflare" / "worker" / "migrations" / "0001_schema.sql"
            database.executescript(schema.read_text(encoding="utf-8"))
            database.executescript(sql)
            imported = database.execute(
                "SELECT plan_day, ethiopian_date, reading, gregorian_date "
                "FROM reading_plan WHERE plan_day IN (17, 231) ORDER BY plan_day"
            ).fetchall()
            row_count = database.execute("SELECT COUNT(*) FROM reading_plan").fetchone()[0]
            database.close()

        self.assertEqual(count, 231)
        self.assertEqual(sql.count("INSERT OR REPLACE INTO reading_plan"), 231)
        self.assertIn("VALUES (17, 'ጥቅምት 17', 'ዘፍጥረት 16-18', '2026-10-27')", sql)
        self.assertIn("VALUES (231, 'ግንቦት 21', 'ነህምያ 10-13 & ሚልክያስ 1-4', '2027-05-29')", sql)
        self.assertEqual(row_count, 231)
        self.assertEqual(
            imported,
            [
                (17, "ጥቅምት 17", "ዘፍጥረት 16-18", "2026-10-27"),
                (231, "ግንቦት 21", "ነህምያ 10-13 & ሚልክያስ 1-4", "2027-05-29"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
