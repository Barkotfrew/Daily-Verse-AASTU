"""Start the Daily Verse Telegram bot using long polling."""

import asyncio
from pathlib import Path

from aiogram import Bot, Dispatcher

from app.bible import JsonBibleRepository
from app.config import load_settings
from app.database import initialize_database
from app.handlers import build_router
from app.reading_plan import load_reading_plan


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
    dispatcher.include_router(build_router(database_path, plan, bible, settings.mini_app_url))
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
