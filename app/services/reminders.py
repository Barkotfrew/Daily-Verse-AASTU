"""Daily 7:00 AM EAT reminder delivery with persistent per-user tracking."""

import asyncio
import logging
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database import (
    due_reminder_deliveries,
    mark_reminder_failed,
    mark_reminder_sent,
    prepare_reminder_deliveries,
    record_reminder_attempt,
    set_reminders_enabled,
)
from app.messages import DAILY_REMINDER
from app.reading_plan import ReadingEntry, ReadingPlan
from app.readings import EAT, entry_for_date

logger = logging.getLogger(__name__)
REMINDER_TIME = time(hour=7)
POLL_SECONDS = 30
BATCH_SIZE = 20
MAX_ATTEMPTS = 5
RETRY_DELAYS_SECONDS = (60, 300, 1800, 21600)


def reminder_text(entry: ReadingEntry) -> str:
    """Render the approved compact template for one shared-plan entry."""
    return DAILY_REMINDER.format(
        day=entry.day,
        ethiopian_date=entry.ethiopian_date,
        gregorian_date=entry.gregorian_date.isoformat(),
        reading=entry.reading,
    )


def reminder_keyboard(day: int, mini_app_url: str) -> InlineKeyboardMarkup:
    read_button = InlineKeyboardButton(text="Mark as Read", callback_data=f"complete:{day}")
    if mini_app_url:
        from urllib.parse import urlencode

        from aiogram.types import WebAppInfo

        read_chapters = InlineKeyboardButton(
            text="Open today's reading",
            web_app=WebAppInfo(url=f"{mini_app_url}/?{urlencode({'day': day})}"),
        )
    else:
        read_chapters = InlineKeyboardButton(
            text="Open today's reading", callback_data=f"chapters:{day}"
        )
    plan_button = InlineKeyboardButton(text="View Reading Plan", callback_data=f"plan:{day}")
    return InlineKeyboardMarkup(inline_keyboard=[[read_chapters], [read_button], [plan_button]])


async def deliver_due_reminders(
    bot: Bot,
    database_path: str | Path,
    plan: ReadingPlan,
    mini_app_url: str = "",
    now: datetime | None = None,
    reminder_time: time = REMINDER_TIME,
) -> int:
    """Deliver due messages for the current shared date and return success count."""
    instant = now or datetime.now(EAT)
    if instant.tzinfo is None:
        raise ValueError("now must include a timezone")
    local_now = instant.astimezone(EAT)
    if local_now.time().replace(tzinfo=None) < reminder_time:
        return 0
    entry = entry_for_date(plan, local_now.date())
    if entry is None:
        return 0

    date_key = local_now.date().isoformat()
    prepare_reminder_deliveries(database_path, date_key, entry.day)
    due = due_reminder_deliveries(
        database_path, date_key, datetime.now(timezone.utc).isoformat(), MAX_ATTEMPTS
    )
    sent_count = 0
    for index, (user_id, chat_id, previous_attempts) in enumerate(due):
        if index and index % BATCH_SIZE == 0:
            await asyncio.sleep(1)
        record_reminder_attempt(database_path, date_key, user_id)
        try:
            await bot.send_message(
                chat_id,
                reminder_text(entry),
                reply_markup=reminder_keyboard(entry.day, mini_app_url),
                request_timeout=15,
            )
        except TelegramForbiddenError as error:
            # A blocked/unreachable private chat should not be retried indefinitely.
            set_reminders_enabled(database_path, user_id, False)
            mark_reminder_failed(database_path, date_key, user_id, str(error), None)
            logger.info("Disabled reminders for Telegram user %s after forbidden delivery", user_id)
        except (TelegramAPIError, asyncio.TimeoutError, OSError) as error:
            attempt_number = previous_attempts + 1
            retry_at = None
            if attempt_number < MAX_ATTEMPTS:
                delay = RETRY_DELAYS_SECONDS[min(attempt_number - 1, len(RETRY_DELAYS_SECONDS) - 1)]
                retry_at = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
            mark_reminder_failed(database_path, date_key, user_id, str(error), retry_at)
            logger.warning("Reminder delivery failed for one user; attempt %s/%s", attempt_number, MAX_ATTEMPTS)
        else:
            mark_reminder_sent(database_path, date_key, user_id)
            sent_count += 1
    return sent_count


async def run_reminder_scheduler(
    bot: Bot,
    database_path: str | Path,
    plan: ReadingPlan,
    mini_app_url: str = "",
    reminder_time: time = REMINDER_TIME,
) -> None:
    """Check every 30 seconds; persistent delivery rows prevent restart duplicates."""
    while True:
        try:
            await deliver_due_reminders(
                bot, database_path, plan, mini_app_url, reminder_time=reminder_time
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Reminder scheduler iteration failed")
        await asyncio.sleep(POLL_SECONDS)
