"""Tests for callback acknowledgement when Telegram expires a button query."""

import unittest
from unittest.mock import AsyncMock, Mock

from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import AnswerCallbackQuery

from app.handlers import _answer_callback


class CallbackAnswerTests(unittest.IsolatedAsyncioTestCase):
    async def test_expired_callback_is_ignored(self) -> None:
        callback = Mock()
        callback.answer = AsyncMock(
            side_effect=TelegramBadRequest(
                method=AnswerCallbackQuery(callback_query_id="expired"),
                message="Bad Request: query is too old and response timeout expired",
            )
        )

        await _answer_callback(callback)

        callback.answer.assert_awaited_once_with()

    async def test_unrelated_telegram_error_is_raised(self) -> None:
        callback = Mock()
        callback.answer = AsyncMock(
            side_effect=TelegramBadRequest(
                method=AnswerCallbackQuery(callback_query_id="bad"),
                message="Bad Request: another failure",
            )
        )

        with self.assertRaises(TelegramBadRequest):
            await _answer_callback(callback)


if __name__ == "__main__":
    unittest.main()
