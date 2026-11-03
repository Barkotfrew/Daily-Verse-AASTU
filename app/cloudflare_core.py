"""Pure helpers shared by Cloudflare Worker handlers and offline tests."""

from datetime import datetime, timedelta, timezone
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
