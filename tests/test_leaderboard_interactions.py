"""Focused tests for interactive, period-aware leaderboard behavior."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from app.cloudflare_core import (
    LEADERBOARD_PAGE_SIZE,
    format_leaderboard_page,
    leaderboard_cutoff_utc,
    leaderboard_keyboard,
    leaderboard_sql,
)
from app.database import (
    initialize_database,
    leaderboard_page,
    leaderboard_rank_context,
)


class LeaderboardInteractionTests(unittest.TestCase):
    def test_eat_period_boundaries_are_converted_to_utc(self):
        # Wednesday 2026-11-18 20:59 UTC is 23:59 EAT.
        now = datetime(2026, 11, 18, 20, 59, tzinfo=timezone.utc)
        self.assertEqual(leaderboard_cutoff_utc("week", now), "2026-11-15 21:00:00")
        self.assertEqual(leaderboard_cutoff_utc("month", now), "2026-10-31 21:00:00")
        self.assertIsNone(leaderboard_cutoff_utc("all", now))
        with self.assertRaises(ValueError):
            leaderboard_cutoff_utc("year", now)

    def test_keyboard_exposes_working_period_page_reader_position_refresh_and_journey_actions(self):
        rows = ({
            "telegram_user_id": 1234567890,
            "display_name": "Barki",
            "academic_year": "2nd year",
            "completed": 3,
            "position": 1,
        },)
        keyboard = leaderboard_keyboard("week", 2, 15, rows)
        buttons = [button for row in keyboard["inline_keyboard"] for button in row]
        callbacks = {button["callback_data"] for button in buttons}
        self.assertIn("lb:p:week:1", callbacks)
        self.assertIn("lb:p:month:1", callbacks)
        self.assertIn("lb:p:all:1", callbacks)
        self.assertIn("lb:r:1234567890:week:2", callbacks)
        self.assertIn("lb:p:week:1", callbacks)  # previous page
        self.assertIn("lb:p:week:3", callbacks)  # next page
        self.assertIn("lb:me:week:2", callbacks)
        self.assertIn("lb:refresh:week:2", callbacks)
        self.assertIn("lb:journey", callbacks)
        self.assertTrue(all(len(callback) <= 64 for callback in callbacks))
        self.assertTrue(any(button["text"] == "✓ This Week" for button in buttons))
        self.assertIn("c.completed_at >= ?", leaderboard_sql("week"))
        self.assertNotIn("completed_at >=", leaderboard_sql("all"))
        self.assertIn("position BETWEEN", leaderboard_sql("all", neighbors=True))

    def test_message_handles_empty_leaderboard_and_timestamp(self):
        text = format_leaderboard_page((), "all", 1, 0,
            datetime(2026, 11, 15, 18, 0, tzinfo=timezone.utc))
        self.assertIn("No readers have joined", text)
        self.assertIn("Updated 21:00 EAT", text)

    def test_period_rankings_pages_and_neighbor_context_only_include_opted_in_readers(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "leaderboard.sqlite3"
            initialize_database(db)
            with closing(sqlite3.connect(db)) as connection, connection:
                recent = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                connection.executemany(
                    "INSERT INTO users (telegram_user_id, display_name, academic_year, department, leaderboard_opt_in) "
                    "VALUES (?, ?, '2nd year', 'ECS', ?)",
                    [(uid, f"Reader {uid:02}", int(uid != 99)) for uid in range(1, 10)]
                    + [(99, "Private reader", 0)],
                )
                # Every reader has old history. Readers 1 and 2 each have one
                # current-period completion, while their all-time counts are 2.
                connection.executemany(
                    "INSERT INTO reading_completions (telegram_user_id, plan_day, completed_at) VALUES (?, ?, ?)",
                    [(uid, 1, "2000-01-01 00:00:00") for uid in range(1, 10)]
                    + [(1, 2, recent), (2, 2, recent)],
                )
                connection.execute(
                    "INSERT OR IGNORE INTO reading_completions "
                    "(telegram_user_id, plan_day, completed_at) VALUES (1, 2, ?)",
                    (recent,),
                )
            page1, total = leaderboard_page(db, "all", 1)
            page2, total2 = leaderboard_page(db, "all", 2)
            weekly, weekly_total = leaderboard_page(db, "week", 1)
            month, _ = leaderboard_page(db, "month", 1)
            context = leaderboard_rank_context(db, "all", 2)
            private_context = leaderboard_rank_context(db, "all", 99)

        self.assertEqual((total, total2, weekly_total), (9, 9, 9))
        self.assertEqual(len(page1), LEADERBOARD_PAGE_SIZE)
        self.assertEqual(len(page2), 2)
        self.assertEqual(page1[0]["completed"], 2)
        self.assertNotEqual(page1[0]["telegram_user_id"], page1[1]["telegram_user_id"])
        self.assertEqual(weekly[0]["telegram_user_id"], 1)
        self.assertEqual(weekly[0]["completed"], 1)
        self.assertEqual(month[0]["completed"], 1)
        self.assertIsNotNone(context)
        own, neighbors = context
        self.assertEqual(own["telegram_user_id"], 2)
        self.assertEqual({row["telegram_user_id"] for row in neighbors}, {1, 2, 3})
        self.assertIsNone(private_context)

    def test_empty_database_has_no_rank_or_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "empty.sqlite3"
            initialize_database(db)
            rows, total = leaderboard_page(db, "all", 1)
            context = leaderboard_rank_context(db, "all", 7)
        self.assertEqual(rows, ())
        self.assertEqual(total, 0)
        self.assertIsNone(context)


if __name__ == "__main__":
    unittest.main()
