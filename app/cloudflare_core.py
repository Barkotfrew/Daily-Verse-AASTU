"""Pure helpers shared by Cloudflare Worker handlers and offline tests."""

from datetime import date, datetime, timedelta, timezone
import hmac
from typing import Any

EAT = timezone(timedelta(hours=3), name="EAT")


def verify_webhook_secret(expected: str, provided: str | None) -> bool:
    """Constant-time compare for Telegram's configured webhook secret header."""
    return bool(expected and provided and hmac.compare_digest(expected, provided))


def scheduled_eat_date(scheduled_timestamp_ms: int) -> str:
    """Convert Cloudflare's UTC scheduled timestamp to the shared EAT date."""
    instant = datetime.fromtimestamp(scheduled_timestamp_ms / 1000, tz=timezone.utc)
    return instant.astimezone(EAT).date().isoformat()


def current_eat_date(now: datetime | None = None) -> date:
    """Return today's date in the community's fixed UTC+3 timezone."""
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("now must include a timezone")
    return instant.astimezone(EAT).date()


def private_message_parts(update: dict[str, Any]) -> tuple[int, int, str] | None:
    """Return (user id, private chat id, text) for a private Telegram message."""
    message = update.get("message")
    if not isinstance(message, dict):
        return None
    chat = message.get("chat")
    user = message.get("from")
    text = message.get("text")
    if (
        not isinstance(chat, dict)
        or chat.get("type") != "private"
        or not isinstance(chat.get("id"), int)
        or not isinstance(user, dict)
        or not isinstance(user.get("id"), int)
        or not isinstance(text, str)
    ):
        return None
    return user["id"], chat["id"], text


def is_start_command(text: str | None) -> bool:
    """Match /start and its optional Telegram bot name or deep-link payload."""
    if not text or not text.strip():
        return False
    first = text.strip().split(maxsplit=1)[0]
    return first.split("@", maxsplit=1)[0].lower() == "/start"


def normalize_display_name(text: str | None) -> str | None:
    """Clean a signup name and reject commands or unusably short/long values."""
    return normalize_signup_value(text, 2, 64)


def normalize_signup_value(text: str | None, minimum: int, maximum: int) -> str | None:
    """Normalize a private signup field and reject commands or invalid lengths."""
    if not isinstance(text, str):
        return None
    value = " ".join(text.split())
    if not minimum <= len(value) <= maximum or value.startswith("/"):
        return None
    return value


def supported_command(text: str) -> str | None:
    """Recognize commands currently ported to the Worker."""
    first = text.strip().split(maxsplit=1)[0] if text.strip() else ""
    command = first.split("@", maxsplit=1)[0].lower()
    if is_start_command(text):
        return "start"
    if command == "/today" or text.strip() == "Today's Reading":
        return "today"
    if command == "/progress" or text.strip() == "My Progress":
        return "progress"
    if command == "/plan" or text.strip() == "Reading Plan":
        return "plan"
    return None


def plan_page_for_command(text: str, total_days: int, page_size: int = 14) -> tuple[int | None, str | None]:
    """Resolve /plan [day] to a page; the argument selects the page containing that day."""
    parts = text.strip().split()
    args = parts[1:] if parts and parts[0].split("@", 1)[0].lower() == "/plan" else []
    if len(args) > 1:
        return None, "Use /plan followed by a day number, for example /plan 17."
    if total_days < 1 or page_size < 1:
        return None, "The reading plan is not available right now."
    if not args:
        return 1, None
    try:
        day = int(args[0])
    except ValueError:
        return None, "Use /plan followed by a day number, for example /plan 17."
    if not 1 <= day <= total_days:
        return None, f"Choose a plan day from 1 to {total_days}."
    return (day - 1) // page_size + 1, None


def format_plan_page(entries: tuple[dict[str, Any], ...], page: int, total_days: int,
                     page_size: int = 14) -> str:
    """Render one bounded D1 result page in the same format as the local bot."""
    total_pages = (total_days + page_size - 1) // page_size
    lines = [
        f"Day {entry['plan_day']} · {entry['ethiopian_date']} · "
        f"{entry['gregorian_date']}\n{entry['reading']}"
        for entry in entries
    ]
    return (
        f"Reading Plan · page {page}/{total_pages} · {total_days} days\n\n"
        + "\n\n".join(lines)
    )


def plan_page_keyboard(page: int, total_days: int, page_size: int = 14) -> dict[str, Any]:
    """Build inline day buttons and bounded previous/next page controls."""
    total_pages = (total_days + page_size - 1) // page_size
    first_day = (page - 1) * page_size + 1
    last_day = min(page * page_size, total_days)
    rows = []
    days = [
        {"text": f"Day {day}", "callback_data": f"plan:{day}"}
        for day in range(first_day, last_day + 1)
    ]
    rows.extend(days[index:index + 2] for index in range(0, len(days), 2))
    navigation = []
    if page > 1:
        navigation.append({"text": "← Previous", "callback_data": f"planpage:{page - 1}"})
    if page < total_pages:
        navigation.append({"text": "Next →", "callback_data": f"planpage:{page + 1}"})
    if navigation:
        rows.append(navigation)
    return {"inline_keyboard": rows}


def plan_day_keyboard(day: int, total_days: int, page_size: int = 14) -> dict[str, Any]:
    """Build safe previous/next day navigation plus the containing plan page."""
    row = []
    if day > 1:
        row.append({"text": "← Previous", "callback_data": f"plan:{day - 1}"})
    if day < total_days:
        row.append({"text": "Next →", "callback_data": f"plan:{day + 1}"})
    rows = [row] if row else []
    rows.append(
        [{"text": "All Plan", "callback_data": f"planpage:{(day - 1) // page_size + 1}"}]
    )
    return {"inline_keyboard": rows}


def registration_required(command: str, registered: bool) -> bool:
    """Require a prior /start registration before serving other commands."""
    return command != "start" and not registered


def format_today_message(entry: dict[str, Any] | None, current_date: date) -> str:
    """Render the plan entry for the shared Gregorian day, if one exists."""
    if entry is None:
        return (
            "There is no scheduled reading for "
            f"{current_date.isoformat()} in this plan."
        )
    return (
        "Today's Reading\n"
        f"Day {entry['plan_day']} · {entry['ethiopian_date']} · "
        f"{entry['gregorian_date']}\n{entry['reading']}"
    )


def format_progress_message(completed: int, total: int, recent_days: tuple[int, ...]) -> str:
    """Format a user's own private completion summary."""
    percentage = completed / total * 100 if total else 0
    history = ", ".join(str(day) for day in recent_days) or "None yet"
    return (
        f"My Progress\n{completed} of {total} readings completed "
        f"({percentage:.1f}%).\nRecent completed days: {history}"
    )


def reminder_message(day: int, ethiopian_date: str, gregorian_date: str, reading: str) -> str:
    """Format the approved fixed reminder text without generated additions."""
    return (
        "ሰላም ተወዳጆች እንዴት ናችሁ? 👋👋👋\n"
        f"የዛሬ ንባብ · ቀን {day}\n"
        f"{ethiopian_date} · {gregorian_date}\n"
        f"{reading}"
    )


def escape_sql_text(value: str) -> str:
    """Quote one SQLite text literal for a generated seed SQL file."""
    return "'" + value.replace("'", "''") + "'"
