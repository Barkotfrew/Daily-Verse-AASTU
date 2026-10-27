"""Small shared-schedule helpers used by Telegram handlers."""

from datetime import date

from app.reading_plan import ReadingEntry, ReadingPlan


def entry_for_date(plan: ReadingPlan, current_date: date) -> ReadingEntry | None:
    """Return the shared reading assigned to this date, if it is in the plan."""
    for entry in plan.entries:
        if entry.gregorian_date == current_date:
            return entry
    return None


def format_reading_entry(entry: ReadingEntry) -> str:
    return (
        f"Day {entry.day} · {entry.ethiopian_date} · "
        f"{entry.gregorian_date.isoformat()}\n{entry.reading}"
    )
