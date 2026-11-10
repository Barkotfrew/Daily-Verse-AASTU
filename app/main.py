"""Start the Daily Verse Telegram bot using long polling."""

import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramNetworkError

from app.bible import JsonBibleRepository
from app.config import load_settings
from app.database import initialize_database
from app.handlers import build_router
from app.reading_plan import load_reading_plan
from app.services.reminders import run_reminder_scheduler

logger = logging.getLogger(__name__)


async def wait_for_telegram(bot: Bot) -> None:
    """Keep startup alive through temporary Telegram API/network outages."""
    delay = 5
    while True:
        try:
            await bot.get_me(request_timeout=15)
            return
        except (TelegramNetworkError, asyncio.TimeoutError, OSError) as error:
            logger.warning(
                "Telegram API is unreachable during startup; retrying in %s seconds: %s",
                delay,
                error,
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)


async def main() -> None:
    settings = load_settings()
    if not settings.bot_token:
        raise SystemExit("BOT_TOKEN is missing. Set it in the project's .env file.")
    database_path = settings.database_path
    if not database_path.is_absolute():
        database_path = Path(__file__).resolve().parent.parent / database_path
    initialize_database(database_path)
    plan = load_reading_plan()
    bible_root = Path(__file__).resolve().parent.parent / "data" / "bible"
    bible_path = bible_root / "normalized_bible.json"
    if not bible_path.is_file():
        bible_path = bible_root / "source" / "amharic_bible.json"
    bible = JsonBibleRepository(bible_path) if bible_path.is_file() else None
    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(build_router(
        database_path,
        plan,
        bible,
        settings.mini_app_url,
        settings.reminder_scheduler_enabled,
        settings.reminder_time,
    ))
    reminder_task = None
    try:
        # Don't start reminder attempts until Telegram is reachable. Otherwise
        # a startup outage can consume a user's reminder retry budget.
        await wait_for_telegram(bot)
        if settings.reminder_scheduler_enabled:
            reminder_task = asyncio.create_task(
                run_reminder_scheduler(
                    bot,
                    database_path,
                    plan,
                    settings.mini_app_url,
                    settings.reminder_time,
                )
            )
        await dispatcher.start_polling(bot)
    finally:
        if reminder_task is not None:
            reminder_task.cancel()
            try:
                await reminder_task
            except asyncio.CancelledError:
                pass
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
