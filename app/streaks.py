"""Pure helpers for displaying verified reading streaks."""

from collections.abc import Iterable


def streak_counts(completed_days: Iterable[int], current_plan_day: int) -> tuple[int, int]:
    """Return (active streak, best streak) using distinct scheduled plan days.

    A streak remains active through the current scheduled day if the user read
    yesterday; it ends after a full missed plan day. No completion is inferred.
    """
    completed = sorted({day for day in completed_days if day > 0})
    if current_plan_day < 1:
        return 0, _longest_run(completed)

    best = _longest_run(completed)
    active_end = current_plan_day if current_plan_day in completed else current_plan_day - 1
    completed_set = set(completed)
    active = 0
    while active_end > 0 and active_end in completed_set:
        active += 1
        active_end -= 1
    return active, best


def _longest_run(days: list[int]) -> int:
    best = run = 0
    previous = 0
    for day in days:
        run = run + 1 if day == previous + 1 else 1
        best = max(best, run)
        previous = day
    return best


def streak_progress_text(current: int, best: int) -> str:
    """Format an understated, compact streak card for Telegram text."""
    return (
        "◆  READING STREAK\n"
        f"{current} day{'s' if current != 1 else ''} in a row\n"
        f"Best · {best} day{'s' if best != 1 else ''}"
    )
