"""Start the Daily Verse Telegram bot using long polling."""

import asyncio
from pathlib import Path

from aiogram import Bot, Dispatcher

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
    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(build_router(database_path, plan))
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
