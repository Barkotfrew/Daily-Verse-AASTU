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

    def test_keyboard_is_minimal_and_pagination_only_appears_when_needed(self):
        keyboard = leaderboard_keyboard("week", 2, 15)
        buttons = [button for row in keyboard["inline_keyboard"] for button in row]
        callbacks = {button["callback_data"] for button in buttons}
        self.assertIn("lb:p:week:1", callbacks)
        self.assertIn("lb:p:month:1", callbacks)
        self.assertIn("lb:p:all:1", callbacks)
        self.assertIn("lb:p:week:3", callbacks)
        self.assertIn("lb:me:week:2", callbacks)
        self.assertNotIn("lb:refresh:week:2", callbacks)
        self.assertFalse(any(callback.startswith("lb:r:") for callback in callbacks))
        self.assertFalse(any("journey" in callback or "top" in callback for callback in callbacks))
        self.assertEqual(len(buttons), 6)  # three periods, Previous/Next, My Position
        self.assertTrue(all(len(callback) <= 64 for callback in callbacks))
        self.assertTrue(any(button["text"] == "✓ This Week" for button in buttons))

        one_page = leaderboard_keyboard("all", 1, 2)
        self.assertEqual(len(one_page["inline_keyboard"]), 2)
        self.assertEqual(one_page["inline_keyboard"][1][0]["callback_data"], "lb:me:all:1")
        self.assertIn("c.completed_at >= ?", leaderboard_sql("week"))
        self.assertNotIn("completed_at >=", leaderboard_sql("all"))
        self.assertIn("position BETWEEN", leaderboard_sql("all", neighbors=True))

    def test_message_is_compact_and_handles_empty_leaderboard(self):
        text = format_leaderboard_page((), "all", 1, 0)
        self.assertIn("No readers have joined", text)
        self.assertNotIn("Updated", text)
        listed = format_leaderboard_page(({
            "telegram_user_id": 7, "display_name": "Barki", "academic_year": "4th year",
            "completed": 1, "position": 1,
        },), "all", 1, 1, viewer_id=7)
        self.assertIn("①  Barki · You · 1 reading", listed)
        self.assertNotIn("Year 4th year", listed)

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
