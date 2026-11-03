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


def supported_command(text: str) -> str | None:
    """Recognize only the first two commands ported to the Worker."""
    first = text.strip().split(maxsplit=1)[0] if text.strip() else ""
    command = first.split("@", maxsplit=1)[0].lower()
    if is_start_command(text):
        return "start"
    if command == "/today" or text.strip() == "Today's Reading":
        return "today"
    return None


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
