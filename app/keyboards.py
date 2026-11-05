"""Shared Telegram reply keyboards."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Today's Reading"), KeyboardButton(text="Reading Plan")],
        [KeyboardButton(text="My Progress"), KeyboardButton(text="Leaderboard")],
        [KeyboardButton(text="Settings")],
        [KeyboardButton(text="Help")],
    ],
    resize_keyboard=True,
)
