"""Require users to start the bot once before using its features."""

from pathlib import Path

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from app.cloudflare_core import is_start_command
from app.database import save_signup_field, signup_stage, user_has_account, user_is_registered
from app.keyboards import MAIN_MENU
from app.messages import (
    REGISTRATION_COMPLETE,
    REGISTRATION_DEPARTMENT_INVALID,
    REGISTRATION_DEPARTMENT_PROMPT,
    REGISTRATION_NAME_INVALID,
    REGISTRATION_NAME_PROMPT,
    REGISTRATION_REQUIRED,
    REGISTRATION_YEAR_INVALID,
    REGISTRATION_YEAR_PROMPT,
)

_PROMPTS = {
    "name": REGISTRATION_NAME_PROMPT,
    "year": REGISTRATION_YEAR_PROMPT,
    "department": REGISTRATION_DEPARTMENT_PROMPT,
}
_INVALID = {
    "name": REGISTRATION_NAME_INVALID,
    "year": REGISTRATION_YEAR_INVALID,
    "department": REGISTRATION_DEPARTMENT_INVALID,
}


class RegistrationGate(BaseMiddleware):
    """Collect signup details after /start, then unlock bot features."""

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
            stage = signup_stage(self.database_path, user.id)
            if event.text and not event.text.strip().startswith("/"):
                if stage in _PROMPTS and save_signup_field(
                    self.database_path, user.id, stage, event.text
                ):
                    next_stage = signup_stage(self.database_path, user.id)
                    if next_stage == "complete":
                        await event.answer(REGISTRATION_COMPLETE, reply_markup=MAIN_MENU)
                    else:
                        await event.answer(_PROMPTS[next_stage])
                else:
                    await event.answer(_INVALID.get(stage, REGISTRATION_NAME_INVALID))
                return None
            stage = signup_stage(self.database_path, user.id)
            await event.answer(_PROMPTS.get(stage, REGISTRATION_NAME_PROMPT))
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
                stage = signup_stage(self.database_path, user.id)
                await event.message.answer(_PROMPTS.get(stage, REGISTRATION_NAME_PROMPT))
        return None
