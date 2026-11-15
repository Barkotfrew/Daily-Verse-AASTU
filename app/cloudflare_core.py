"""Pure helpers shared by Cloudflare Worker handlers and offline tests."""

from datetime import date, datetime, timedelta, timezone
import hmac
from typing import Any
from urllib.parse import urlencode

try:
    from app.references import BOOKS, ReferenceParseError, parse_reading_assignment
except ModuleNotFoundError as exc:
    if exc.name != "app":
        raise
    from references import BOOKS, ReferenceParseError, parse_reading_assignment

EAT = timezone(timedelta(hours=3), name="EAT")
JOURNEY_PAGE_SIZE = 6


def page_for_day(day: int, page_size: int = 14) -> int:
    """Return the one-based shared-plan page containing a valid day."""
    if day < 1 or page_size < 1:
        raise ValueError("day and page size must be positive")
    return (day - 1) // page_size + 1


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

LEADERBOARD_POSITION_QUERY = """WITH scores AS (
    SELECT u.telegram_user_id, u.display_name, COUNT(c.plan_day) AS completed
    FROM users AS u LEFT JOIN reading_completions AS c
      ON c.telegram_user_id = u.telegram_user_id
    WHERE u.leaderboard_opt_in = 1
      AND u.display_name IS NOT NULL AND trim(u.display_name) != ''
      AND u.academic_year IS NOT NULL AND trim(u.academic_year) != ''
      AND u.department IS NOT NULL AND trim(u.department) != ''
    GROUP BY u.telegram_user_id, u.display_name, u.academic_year
), ranked AS (
    SELECT telegram_user_id, completed,
           ROW_NUMBER() OVER (
               ORDER BY completed DESC, display_name COLLATE NOCASE, telegram_user_id
           ) AS position
    FROM scores
)
SELECT position, completed FROM ranked WHERE telegram_user_id = ?"""


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
    """Build an interactive today's-reading keyboard with reading and reflection actions."""
    rows = []
    reader = mini_app_reader_keyboard(base_url, day)
    if reader:
        rows.extend(reader["inline_keyboard"])
        reflection_url = mini_app_reader_url(base_url, day=day)
        if reflection_url:
            params = urlencode({"day": day, "journal": 1})
            rows.append([{
                "text": "📝 Reflect",
                "web_app": {"url": f"{base_url.rstrip('/')}/?{params}"},
            }])
    rows.append([{
        "text": "✅ Reading complete" if completed else "✅ Mark as Read",
        "callback_data": f"complete:{day}",
    }])
    rows.append([{
        "text": "🗓 View Reading Plan",
        # Keep this calculation local to the keyboard builder. In the deployed
        # Worker bundle, this helper has previously been missing at runtime.
        "callback_data": f"planpage:{(day - 1) // 14 + 1}",
    }])
    return {"inline_keyboard": rows}


def completion_button(
    day: int, completed: bool = False, callback_prefix: str = "complete"
) -> list[dict[str, str]]:
    return [{
        "text": "✓ Read" if completed else "Mark as Read",
        "callback_data": f"{callback_prefix}:{day}",
    }]


def reminders_keyboard(enabled: bool) -> dict[str, Any]:
    return {"inline_keyboard": [[{
        "text": "Reminders · 06:00, 12:00, 18:00 EAT",
        "callback_data": "reminders:info",
    }]]}


def reminders_settings_message(enabled: bool) -> str:
    return (
        "Daily reminders are sent automatically to everyone who has started the bot.\n"
        "Schedule: 06:00, 12:00, and 18:00 EAT."
    )


def leaderboard_settings_message(enabled: bool) -> str:
    consent = (
        "Your chosen name, study year, and completed-reading count appear on the shared list."
        if enabled
        else "You are not listed. Join to share your chosen name, study year, and completed-reading count."
    )
    return f"Leaderboard\n{consent}\nThe same list is shown to everyone who opens it."


def settings_keyboard(reminders_enabled: bool, leaderboard_enabled: bool) -> dict[str, Any]:
    """Settings actions; reminders are automatic and leaderboard stays opt-in."""
    leaderboard_label = "Leave leaderboard" if leaderboard_enabled else "Join leaderboard"
    return {"inline_keyboard": [
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


def format_leaderboard_message(
    rows: tuple[dict[str, Any], ...],
    current_user_position: int | None = None,
    current_user_completed: int | None = None,
) -> str:
    """Render a restrained community leaderboard and mark the viewer's position."""
    if not rows:
        return "Reading together\n\nNo opted-in readers yet. Join from Settings if you’d like to take part."
    lines = ["Reading together", "Bible plan completions · opted-in readers", ""]
    for rank, row in enumerate(rows, start=1):
        marker = {1: "①", 2: "②", 3: "③"}.get(rank, f"{rank:02d}")
        you = " · You" if current_user_position == rank else ""
        lines.extend((
            f"{marker}  {row['display_name']}  ·  Year {row['academic_year']}{you}",
            f"   ✓ {row['completed']} readings",
        ))
    if current_user_position is not None and current_user_position > len(rows):
        lines.extend((
            "",
            f"Your place: #{current_user_position}  ·  {current_user_completed or 0} readings",
        ))
    return "\n".join(lines)


LEADERBOARD_PERIODS = {"week": "This Week", "month": "This Month", "all": "All Time"}
LEADERBOARD_PAGE_SIZE = 7


def leaderboard_cutoff_utc(period: str, now: datetime | None = None) -> str | None:
    """Return the UTC timestamp at the start of the selected EAT reporting period."""
    if period not in LEADERBOARD_PERIODS:
        raise ValueError("unknown leaderboard period")
    if period == "all":
        return None
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    local = instant.astimezone(EAT)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        start -= timedelta(days=local.weekday())
    else:
        start = start.replace(day=1)
    return start.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def leaderboard_sql(period: str, *, paged: bool = False, selected_user: bool = False,
                   neighbors: bool = False) -> str:
    """Build a ranking query; period names are validated before SQL is formed."""
    cutoff = " AND c.completed_at >= ?" if period in {"week", "month"} else ""
    if period not in LEADERBOARD_PERIODS:
        raise ValueError("unknown leaderboard period")
    if selected_user and neighbors:
        raise ValueError("choose either one reader or adjacent readers")
    selector = (
        "WHERE telegram_user_id = ?" if selected_user else
        "WHERE position BETWEEN (SELECT position-1 FROM ranked WHERE telegram_user_id = ?) "
        "AND (SELECT position+1 FROM ranked WHERE telegram_user_id = ?)" if neighbors else ""
    )
    page_clause = "LIMIT ? OFFSET ?" if paged else ""
    return f"""WITH scores AS (
        SELECT u.telegram_user_id, u.display_name, u.academic_year,
               COUNT(c.plan_day) AS completed
        FROM users AS u LEFT JOIN reading_completions AS c
          ON c.telegram_user_id = u.telegram_user_id{cutoff}
        WHERE u.leaderboard_opt_in = 1
          AND u.display_name IS NOT NULL AND trim(u.display_name) != ''
          AND u.academic_year IS NOT NULL AND trim(u.academic_year) != ''
          AND u.department IS NOT NULL AND trim(u.department) != ''
        GROUP BY u.telegram_user_id, u.display_name, u.academic_year
    ), ranked AS (
        SELECT telegram_user_id, display_name, academic_year, completed,
               ROW_NUMBER() OVER (ORDER BY completed DESC, display_name COLLATE NOCASE,
                                  telegram_user_id) AS position
        FROM scores
    )
    SELECT telegram_user_id, display_name, academic_year, completed, position
    FROM ranked {selector}
    ORDER BY position {page_clause}"""


def leaderboard_keyboard(period: str, page: int, total: int) -> dict[str, Any]:
    """Create only period, optional paging, and personal-position actions."""
    if period not in LEADERBOARD_PERIODS or page < 1:
        raise ValueError("invalid leaderboard state")
    total_pages = max(1, (total + LEADERBOARD_PAGE_SIZE - 1) // LEADERBOARD_PAGE_SIZE)
    page = min(page, total_pages)
    buttons = [[{
        "text": ("✓ " if key == period else "") + label,
        "callback_data": f"lb:p:{key}:1",
    } for key, label in LEADERBOARD_PERIODS.items()]]
    nav = []
    if total_pages > 1 and page > 1:
        nav.append({"text": "← Previous", "callback_data": f"lb:p:{period}:{page - 1}"})
    if total_pages > 1 and page < total_pages:
        nav.append({"text": "Next →", "callback_data": f"lb:p:{period}:{page + 1}"})
    if nav:
        buttons.append(nav)
    buttons.append([{"text": "My Position", "callback_data": f"lb:me:{period}:{page}"}])
    return {"inline_keyboard": buttons}


def format_leaderboard_page(rows, period: str, page: int, total: int,
                            viewer_id: int | None = None) -> str:
    """Render one concise ranked list with restrained top-three cues."""
    if period not in LEADERBOARD_PERIODS:
        raise ValueError("unknown leaderboard period")
    total_pages = max(1, (total + LEADERBOARD_PAGE_SIZE - 1) // LEADERBOARD_PAGE_SIZE)
    first_rank = (page - 1) * LEADERBOARD_PAGE_SIZE + 1
    last_rank = min(first_rank + len(rows) - 1, total)
    range_text = f"Readers {first_rank}–{last_rank} of {total}" if rows else "No readers"
    heading = [f"READING TOGETHER · {LEADERBOARD_PERIODS[period].upper()}",
               f"{range_text} · Page {page}/{total_pages}", ""]
    if not rows:
        return "\n".join(heading + ["No readers have joined yet. You can opt in from Settings."])
    for row in rows:
        rank = int(row["position"])
        marker = {1: "①", 2: "②", 3: "③"}.get(rank, f"{rank:02d}")
        you = " · You" if viewer_id == int(row["telegram_user_id"]) else ""
        count = int(row["completed"])
        heading.append(f"{marker}  {row['display_name']}{you} · {count} reading{'s' if count != 1 else ''}")
    return "\n".join(heading)


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


def format_today_message(
    entry: dict[str, Any] | None,
    current_date: date,
    completed: bool = False,
) -> str:
    """Render the plan entry for the shared Gregorian day, if one exists."""
    if entry is None:
        return (
            "There is no scheduled reading for "
            f"{current_date.isoformat()} in this plan."
        )
    next_step = (
        "✅ You’ve marked this reading complete. Well done!"
        if completed
        else "Take a little time with today’s chapters. When you finish, mark them complete or write a private reflection."
    )
    return (
        "📖 TODAY’S READING\n"
        f"Day {entry['plan_day']} · {entry['ethiopian_date']} · "
        f"{entry['gregorian_date']}\n{entry['reading']}\n\n"
        f"{next_step}"
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


def completed_this_eat_week(records, now: datetime | None = None) -> int:
    """Count distinct completions in the current Monday–Sunday EAT week."""
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    today = instant.astimezone(EAT).date()
    week_start = today - timedelta(days=today.weekday())
    count = 0
    for _day, raw_timestamp in records:
        try:
            completed_at = datetime.fromisoformat(str(raw_timestamp))
        except (TypeError, ValueError):
            continue
        if completed_at.tzinfo is None:
            completed_at = completed_at.replace(tzinfo=timezone.utc)
        local_date = completed_at.astimezone(EAT).date()
        if week_start <= local_date <= today:
            count += 1
    return count


def books_visited_count(entries, completed_days) -> int:
    """Count canonical Bible books in actually completed scheduled readings."""
    completed = set(completed_days)
    visited = set()
    for entry in entries:
        day = entry.get("plan_day", entry.get("day")) if isinstance(entry, dict) else entry.day
        if day not in completed:
            continue
        reading = entry.get("reading") if isinstance(entry, dict) else entry.reading
        try:
            visited.update(passage.book.id for passage in parse_reading_assignment(reading))
        except ReferenceParseError:
            continue
    return len(visited)


def journey_progress_message(
    completed: int,
    total: int,
    week_count: int,
    books_visited: int,
    current_entry,
    current_completed: bool,
    streak: str,
) -> str:
    """Render a restrained, personal reading-plan summary."""
    percentage = completed / total if total else 0
    filled = round(percentage * 10)
    bar = "■" * filled + "·" * (10 - filled)
    if current_entry is None:
        current = "No reading is scheduled for today."
    else:
        day = current_entry.get("plan_day", current_entry.get("day")) if isinstance(current_entry, dict) else current_entry.day
        ethiopian_date = current_entry.get("ethiopian_date") if isinstance(current_entry, dict) else current_entry.ethiopian_date
        reading = current_entry.get("reading") if isinstance(current_entry, dict) else current_entry.reading
        status = "You’ve completed this reading." if current_completed else "This reading is still open for you."
        current = f"Day {day} · {ethiopian_date}\n{reading}\n{status}"
    return (
        "DAILY VERSE · PERSONAL RECORD\n"
        "My Reading Journey\n\n"
        f"{completed} of {total} shared-plan readings completed\n"
        f"{bar}  {percentage:.0%}\n"
        "Progress follows the shared reading plan.\n\n"
        "CURRENT SHARED READING\n"
        f"{current}\n\n"
        "YOUR RECORD\n"
        f"Completed readings · {completed}\n"
        f"This week · {week_count}\n"
        f"Bible books visited · {books_visited}\n\n"
        f"{streak}"
    )


def journey_timeline_page(entries, completed_days, current_day: int | None, page: int,
                          page_size: int = JOURNEY_PAGE_SIZE):
    """Return canonical-order entries and a restrained timeline page heading."""
    ordered = tuple(sorted(entries, key=lambda item: (
        item.get("plan_day", item.get("day")) if isinstance(item, dict) else item.day
    )))
    if not ordered:
        return None, 0, "The shared reading plan is not available right now."
    if page_size < 1:
        return None, 1, "That timeline page is unavailable."
    total_pages = max(1, (len(ordered) + page_size - 1) // page_size)
    if page < 1 or page > total_pages:
        return None, total_pages, "That timeline page is unavailable."
    start = (page - 1) * page_size
    selected = ordered[start:start + page_size]
    labels = []
    for item in selected:
        day = item.get("plan_day", item.get("day")) if isinstance(item, dict) else item.day
        ethiopian_date = item.get("ethiopian_date") if isinstance(item, dict) else item.ethiopian_date
        reading = item.get("reading") if isinstance(item, dict) else item.reading
        marker = (
            "✓◉" if day in completed_days and day == current_day else
            "✓" if day in completed_days else
            "◉" if day == current_day else
            "○" if current_day and day < current_day else "·"
        )
        labels.append(f"{marker} Day {day} · {ethiopian_date}\n   {reading}")
    first = start + 1
    last = start + len(selected)
    first_date = selected[0].get("ethiopian_date") if isinstance(selected[0], dict) else selected[0].ethiopian_date
    last_date = selected[-1].get("ethiopian_date") if isinstance(selected[-1], dict) else selected[-1].ethiopian_date
    heading = (
        f"READING TIMELINE · {page}/{total_pages}\n"
        f"Days {first}–{last} of {len(ordered)} · {first_date}–{last_date}\n\n"
    )
    return selected, total_pages, heading + "\n\n".join(labels) + "\n\n✓ completed · ◉ current · ○ not completed · · upcoming"


def journey_timeline_keyboard(entries, page: int, total_pages: int,
                              page_size: int = JOURNEY_PAGE_SIZE):
    """Build compact timeline entry and pagination callback buttons."""
    rows = []
    for item in entries:
        day = item.get("plan_day", item.get("day")) if isinstance(item, dict) else item.day
        reading = item.get("reading") if isinstance(item, dict) else item.reading
        rows.append([{"text": f"Day {day} · {reading[:24]}", "callback_data": f"journey:entry:{day}"}])
    navigation = []
    if page > 1:
        navigation.append({"text": "← Previous", "callback_data": f"journey:timeline:{page - 1}"})
    if page < total_pages:
        navigation.append({"text": "Next →", "callback_data": f"journey:timeline:{page + 1}"})
    if navigation:
        rows.append(navigation)
    rows.append([{"text": "My Reading Journey", "callback_data": "journey:home"}])
    return {"inline_keyboard": rows}


def reminder_message(
    day: int, ethiopian_date: str, gregorian_date: str, reading: str,
    schedule_slot: str = "12:00",
) -> str:
    """Format the approved 12:00 or 18:00 EAT reminder copy."""
    if schedule_slot == "18:00":
        return (
            "If you haven't read today's portion yet, this is your little reminder. ❤️\n\n"
            "There's still time! Let's not miss today's time in the Word. 📖"
        )
    return (
        "🔔 Just a little reminder, ተወዳጆች!\n\n"
        "Have you had your time in God's Word today? Today's reading is waiting for you. 📖"
    )


def morning_reminder_message(day: int, ethiopian_date: str, gregorian_date: str, reading: str) -> str:
    """Format the warm 06:00 EAT opening reminder."""
    return (
        "ሰላም ተወዳጆች! 👋\n"
        "ንባባችን እንደቀጠለ ነው!!\n\n"
        "Let's start our day with God's Word! Here's today's portion of our Challenge. 📖\n\n"
        "📖 *TODAY'S READING*\n\n"
        f"Day {day} · {ethiopian_date} · {gregorian_date}\n\n"
        f"*{reading}*\n\n"
        "Take a little time to read and reflect on today's chapters.\n\n"
        "Have a blessed day!"
    )


def escape_sql_text(value: str) -> str:
    """Quote one SQLite text literal for a generated seed SQL file."""
    return "'" + value.replace("'", "''") + "'"
