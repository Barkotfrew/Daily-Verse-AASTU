"""Small shared-schedule helpers used by Telegram handlers."""

from datetime import date, datetime, timedelta, timezone

from app.reading_plan import ReadingEntry, ReadingPlan

EAT = timezone(timedelta(hours=3), name="EAT")
PLAN_PAGE_SIZE = 14


def eat_date(now: datetime | None = None) -> date:
    """Return the current date in Ethiopia's fixed UTC+3 timezone."""
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("now must include a timezone")
    return instant.astimezone(EAT).date()


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


def plan_page_count(plan: ReadingPlan, page_size: int = PLAN_PAGE_SIZE) -> int:
    if page_size < 1:
        raise ValueError("page_size must be positive")
    return (plan.total_days + page_size - 1) // page_size


def page_for_day(day: int, page_size: int = PLAN_PAGE_SIZE) -> int:
    if day < 1 or page_size < 1:
        raise ValueError("day and page_size must be positive")
    return (day - 1) // page_size + 1


def format_plan_page(
    plan: ReadingPlan, page: int, page_size: int = PLAN_PAGE_SIZE
) -> str:
    """Format one bounded page of the plan for Telegram's message view."""
    total_pages = plan_page_count(plan, page_size)
    if page < 1 or page > total_pages:
        raise ValueError(f"page must be between 1 and {total_pages}")
    first = (page - 1) * page_size
    entries = plan.entries[first:first + page_size]
    rows = [
        f"Day {entry.day} · {entry.ethiopian_date} · {entry.gregorian_date.isoformat()}\n"
        f"{entry.reading}"
        for entry in entries
    ]
    return (
        f"Reading Plan · page {page}/{total_pages} · {plan.total_days} days\n\n"
        + "\n\n".join(rows)
    )
