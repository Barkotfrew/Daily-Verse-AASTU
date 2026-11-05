import unittest

from app.streaks import streak_counts, streak_progress_text


class StreakTests(unittest.TestCase):
    def test_counts_consecutive_active_and_best_runs(self) -> None:
        self.assertEqual(streak_counts((1, 2, 4, 5, 6), current_plan_day=7), (3, 3))

    def test_today_can_be_pending_without_breaking_yesterdays_streak(self) -> None:
        self.assertEqual(streak_counts((1, 2, 3), current_plan_day=4), (3, 3))

    def test_missed_day_ends_active_run_but_keeps_best(self) -> None:
        self.assertEqual(streak_counts((1, 2, 4, 5), current_plan_day=7), (0, 2))

    def test_duplicate_completions_are_counted_once(self) -> None:
        self.assertEqual(streak_counts((3, 3, 4, 4), current_plan_day=5), (2, 2))

    def test_empty_and_pre_plan_state(self) -> None:
        self.assertEqual(streak_counts((), current_plan_day=1), (0, 0))
        self.assertEqual(streak_counts((1, 2), current_plan_day=0), (0, 2))

    def test_progress_display_stays_compact(self) -> None:
        text = streak_progress_text(3, 8)
        self.assertIn("3 days in a row", text)
        self.assertIn("Best · 8 days", text)


if __name__ == "__main__":
    unittest.main()
