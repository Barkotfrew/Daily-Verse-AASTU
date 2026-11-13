"""Pure helpers shared by Cloudflare Worker handlers and offline tests."""

from datetime import date, datetime, timedelta, timezone
import hmac
from typing import Any
from urllib.parse import urlencode

try:
    from app.references import BOOKS
except ModuleNotFoundError as exc:
    if exc.name != "app":
        raise
    from references import BOOKS

EAT = timezone(timedelta(hours=3), name="EAT")

LEADERBOARD_QUERY = """SELECT u.display_name, u.academic_year,
       COUNT(c.plan_day) AS completed
FROM users AS u LEFT JOIN reading_completions AS c
  ON c.telegram_user_id = u.telegram_user_id
WHERE u.leaderboard_opt_in = 1
  AND u.display_name IS NOT NULL AND trim(u.display_name) != ''
  AND u.academic_year IS NOT NULL AND trim(u.academic_year) != ''
  AND u.department IS NOT NULL AND trim(u.department) != ''
GROUP BY u.telegram_user_id, u.display_name, u.academic_year
ORDER BY completed DESC, u.display_name COLLATE NOCASE, u.telegram_user_id
LIMIT 10"""


def mini_app_reader_url(
    base_url: str,
    *,
    day: int | None = None,
    book_id: str | None = None,
    chapter: int | None = None,
) -> str | None:
    """Build a safe HTTPS URL for an assigned day or canonical chapter."""
    base = base_url.rstrip("/")
    if not base.startswith("https://"):
        return None
    if isinstance(day, int) and not isinstance(day, bool) and day > 0:
        query = urlencode({"day": day})
    elif (
        book_id in {book.id for book in BOOKS}
        and isinstance(chapter, int)
        and not isinstance(chapter, bool)
        and 1 <= chapter <= 150
    ):
        query = urlencode({"book": book_id, "chapter": chapter})
    else:
        return None
    return f"{base}/?{query}"


def mini_app_chapter_asset_url(base_url: str, book_id: str, chapter: int) -> str | None:
    """Build a Pages chapter asset URL only for known books and bounded chapters."""
    base = base_url.rstrip("/")
    valid_book = any(book.id == book_id for book in BOOKS)
    if not base.startswith("https://") or not valid_book:
        return None
    if not isinstance(chapter, int) or isinstance(chapter, bool) or not 1 <= chapter <= 150:
        return None
    return f"{base}/assets/chapters/{book_id}/{chapter}.json"


def mini_app_reader_keyboard(base_url: str, day: int) -> dict[str, Any] | None:
    """Build the private-chat button that opens that day's assigned chapters."""
    url = mini_app_reader_url(base_url, day=day)
    if url is None:
        return None
    return {
        "inline_keyboard": [[{
            "text": "Read Chapters",
            "web_app": {"url": url},
        }]],
    }


def reminder_keyboard(base_url: str, day: int) -> dict[str, Any]:
    """Open today's assigned chapters directly from a scheduled reminder."""
    url = mini_app_reader_url(base_url, day=day)
    button = {"text": "Open today's reading"}
    if url:
        button["web_app"] = {"url": url}
    else:
        button["callback_data"] = f"plan:{day}"
    return {"inline_keyboard": [[button]]}


def today_keyboard(base_url: str, day: int, completed: bool = False) -> dict[str, Any]:
    """Build a private today's-reading keyboard with explicit completion."""
    rows = [[{
        "text": "✓ Read" if completed else "Mark as Read",
        "callback_data": f"complete:{day}",
    }]]
    reader = mini_app_reader_keyboard(base_url, day)
    if reader:
        rows.extend(reader["inline_keyboard"])
    return {"inline_keyboard": rows}


def completion_button(
    day: int, completed: bool = False, callback_prefix: str = "complete"
) -> list[dict[str, str]]:
    return [{
        "text": "✓ Read" if completed else "Mark as Read",
        "callback_data": f"{callback_prefix}:{day}",
    }]


def reminders_keyboard(enabled: bool) -> dict[str, Any]:
    label = "Turn reminders off" if enabled else "Turn reminders on"
    return {"inline_keyboard": [[{
        "text": label,
        "callback_data": "reminders:toggle",
    }]]}


def reminders_settings_message(enabled: bool) -> str:
    state = "on" if enabled else "off"
    return (
        f"Settings\nDaily reminders are {state}.\n"
        "Reminders continue after you mark a reading complete."
    )


def leaderboard_settings_message(enabled: bool) -> str:
    consent = (
        "Your chosen name, study year, and completed-reading count appear on the shared list."
        if enabled
        else "You are not listed. Join to share your chosen name, study year, and completed-reading count."
    )
    return f"Leaderboard\n{consent}\nThe same list is shown to everyone who opens it."


def settings_keyboard(reminders_enabled: bool, leaderboard_enabled: bool) -> dict[str, Any]:
    """Settings actions, with leaderboard visibility controlled by explicit opt-in."""
    reminder_label = "Turn reminders off" if reminders_enabled else "Turn reminders on"
    leaderboard_label = "Leave leaderboard" if leaderboard_enabled else "Join leaderboard"
    return {"inline_keyboard": [
        [{"text": reminder_label, "callback_data": "reminders:toggle"}],
        [{"text": leaderboard_label, "callback_data": "leaderboard:toggle"}],
        [{"text": "Edit my details", "callback_data": "profile:edit"}],
        [{"text": "Delete my account", "callback_data": "account:delete"}],
    ]}


def profile_edit_keyboard() -> dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "Edit name", "callback_data": "profile:field:display_name"}],
        [{"text": "Edit year of study", "callback_data": "profile:field:academic_year"}],
        [{"text": "Edit department", "callback_data": "profile:field:department"}],
        [{"text": "Cancel", "callback_data": "profile:cancel"}],
    ]}


def account_delete_keyboard() -> dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "Confirm deletion", "callback_data": "account:confirm"}],
        [{"text": "Cancel", "callback_data": "account:cancel"}],
    ]}


def format_leaderboard_message(rows: tuple[dict[str, Any], ...]) -> str:
    """Render stable leaderboard rows with only consented public fields."""
    if not rows:
        return "Reading leaderboard\n\nNo readers have joined yet. Join from Settings to appear here."
    lines = ["Reading leaderboard", "Opted-in readers · completed readings", ""]
    lines.extend(
        f"{rank:02d}  {row['display_name']}  ·  Year {row['academic_year']}  ·  "
        f"{row['completed']} readings"
        for rank, row in enumerate(rows, start=1)
    )
    return "\n".join(lines)


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
    if command == "/progress" or text.strip() in {"My Progress", "My Reading Journey 🌱"}:
        return "progress"
    if command == "/journal" or text.strip() == "My Journal":
        return "journal"
    if command == "/leaderboard" or text.strip() == "Leaderboard":
        return "leaderboard"
    if command == "/settings" or text.strip() == "Settings":
        return "settings"
    if command == "/plan" or text.strip() == "Reading Plan":
        return "plan"
    if command == "/help" or text.strip() == "Help":
        return "help"
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
    return command not in {"start", "help"} and not registered


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


def format_progress_message(
    completed: int,
    total: int,
    recent_days: tuple[int, ...],
    streak: str | None = None,
) -> str:
    """Format a user's own private completion summary."""
    percentage = completed / total * 100 if total else 0
    history = ", ".join(f"Day {day}" for day in recent_days) or "No completed days yet"
    streak_section = f"\n{streak}\n" if streak else ""
    return (
        f"🌱 Your Reading Journey{streak_section}\n"
        f"📖 {completed} of {total} assigned readings completed ({percentage:.1f}%).\n"
        "Every reading is a step forward—keep going at your own pace!\n\n"
        "Recently completed\n"
        f"{history}\n\n"
        "This tracks the shared reading plan, not whole-Bible coverage."
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
