"""Require users to start the bot once before using its features."""

from pathlib import Path

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from app.cloudflare_core import is_start_command
from app.database import save_display_name, user_has_account, user_is_registered
from app.keyboards import MAIN_MENU
from app.messages import (
    REGISTRATION_COMPLETE,
    REGISTRATION_NAME_INVALID,
    REGISTRATION_NAME_PROMPT,
    REGISTRATION_REQUIRED,
)


class RegistrationGate(BaseMiddleware):
    """Collect a chosen name after /start, then unlock bot features."""

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
            if event.chat.type != "private":
                await event.answer("Please register in a private chat with the bot.")
                return None
            if not user_has_account(self.database_path, user.id):
                await event.answer(REGISTRATION_REQUIRED)
                return None
            if event.text and not event.text.strip().startswith("/"):
                if save_display_name(self.database_path, user.id, event.text):
                    await event.answer(REGISTRATION_COMPLETE, reply_markup=MAIN_MENU)
                else:
                    await event.answer(REGISTRATION_NAME_INVALID)
                return None
            await event.answer(REGISTRATION_NAME_PROMPT)
        elif isinstance(event, CallbackQuery):
            try:
                await event.answer(REGISTRATION_REQUIRED, show_alert=True)
            except TelegramBadRequest as error:
                message = str(error).lower()
                if "query is too old" not in message and "query id is invalid" not in message:
                    raise
            if (
                event.message
                and event.message.chat.type == "private"
                and user_has_account(self.database_path, user.id)
            ):
                await event.message.answer(REGISTRATION_NAME_PROMPT)
        return None
