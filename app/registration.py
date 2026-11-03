"""Require users to start the bot once before using its features."""

from pathlib import Path

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from app.cloudflare_core import is_start_command
from app.database import user_is_registered
from app.messages import REGISTRATION_REQUIRED


class RegistrationGate(BaseMiddleware):
    """Block message and button features until /start created the user row."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = database_path

    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if user is None:
            return await handler(event, data)

        if isinstance(event, Message) and is_start_command(event.text):
            return await handler(event, data)

        if user_is_registered(self.database_path, user.id):
            return await handler(event, data)

        if isinstance(event, Message):
            await event.answer(REGISTRATION_REQUIRED)
        elif isinstance(event, CallbackQuery):
            try:
                await event.answer(REGISTRATION_REQUIRED, show_alert=True)
            except TelegramBadRequest as error:
                message = str(error).lower()
                if "query is too old" not in message and "query id is invalid" not in message:
                    raise
        return None
