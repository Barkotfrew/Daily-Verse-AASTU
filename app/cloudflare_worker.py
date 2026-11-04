"""Cloudflare Worker entry point for the incremental hosting migration.

Private signup, /today, /progress, and paged /plan browsing are implemented.
Do not set the production Telegram webhook until all commands, inline search,
and reminder delivery have been migrated and tested.
"""

import json
from urllib.parse import urlparse

from workers import Response, WorkerEntrypoint, fetch
from js import Object
from pyodide.ffi import to_js

from cloudflare_core import (
    current_eat_date,
    format_progress_message,
    format_today_message,
    format_plan_page,
    normalize_signup_value,
    plan_page_for_command,
    plan_day_keyboard,
    plan_page_keyboard,
    private_message_parts,
    registration_required,
    supported_command,
    verify_webhook_secret,
)
from messages import REGISTRATION_COMPLETE, REGISTRATION_EXISTING, REGISTRATION_REQUIRED

REGISTRATION_NAME_PROMPT = (
    "What is your name?\n"
    "It may appear on a future reading leaderboard."
)
REGISTRATION_NAME_INVALID = "Please enter your name using 2 to 64 characters."
REGISTRATION_YEAR_PROMPT = "What year of study are you in? For example: 2nd year."
REGISTRATION_DEPARTMENT_PROMPT = "What is your department?"
REGISTRATION_YEAR_INVALID = "Please enter your year of study, such as 2 or 2nd year."
REGISTRATION_DEPARTMENT_INVALID = "Please enter a department name between 2 and 80 characters."


def next_signup_field(user):
    if not user["display_name"]:
        return "display_name"
    if not user["academic_year"]:
        return "academic_year"
    if not user["department"]:
        return "department"
    return None


def signup_prompt(field):
    return {
        "display_name": REGISTRATION_NAME_PROMPT,
        "academic_year": REGISTRATION_YEAR_PROMPT,
        "department": REGISTRATION_DEPARTMENT_PROMPT,
    }.get(field, REGISTRATION_NAME_PROMPT)


MAIN_MENU = {
    "keyboard": [
        [{"text": "Today's Reading"}, {"text": "Reading Plan"}],
        [{"text": "My Progress"}, {"text": "Settings"}],
        [{"text": "Help"}],
    ],
    "resize_keyboard": True,
}


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        path = urlparse(request.url).path

        if request.method == "GET" and path == "/health":
            row = await self.env.DB.prepare(
                "SELECT COUNT(*) AS total FROM reading_plan"
            ).first()
            total = int(row["total"]) if row else 0
            return Response.json(
                {"status": "ok", "plan_loaded": total > 0, "plan_days": total}
            )

        if request.method == "POST" and path == "/telegram/webhook":
            expected = getattr(self.env, "TELEGRAM_WEBHOOK_SECRET", "")
            provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if not verify_webhook_secret(expected, provided):
                return Response("Unauthorized", status=401)

            try:
                update = await request.json()
            except Exception:
                return Response("Invalid JSON", status=400)

            callback = update.get("callback_query")
            if isinstance(callback, dict):
                await self._handle_plan_callback(callback)
                return Response("OK")

            parts = private_message_parts(update)
            if parts is None:
                # Ignore update types and non-private chats we do not support.
                # Returning 503 makes Telegram repeatedly deliver the same update.
                return Response("OK")
            user_id, chat_id, text = parts
            command = supported_command(text)
            if command is None:
                user = await self.env.DB.prepare(
                    "SELECT display_name, academic_year, department FROM users "
                    "WHERE telegram_user_id = ?"
                ).bind(user_id).first()
                field = next_signup_field(user) if user is not None else None
                if field is None:
                    if user is None:
                        await self._send_message(chat_id, REGISTRATION_REQUIRED)
                    else:
                        await self._send_message(
                            chat_id,
                            "Please use the menu buttons or /help to see available options.",
                            MAIN_MENU,
                        )
                    return Response("OK")
                minimum, maximum, invalid = {
                    "display_name": (2, 64, REGISTRATION_NAME_INVALID),
                    "academic_year": (1, 24, REGISTRATION_YEAR_INVALID),
                    "department": (2, 80, REGISTRATION_DEPARTMENT_INVALID),
                }[field]
                value = normalize_signup_value(text, minimum, maximum)
                if value is None:
                    await self._send_message(chat_id, invalid)
                else:
                    await self.env.DB.prepare(
                        f"UPDATE users SET {field} = ?, private_chat_id = ? "
                        f"WHERE telegram_user_id = ? AND {field} IS NULL"
                    ).bind(value, chat_id, user_id).run()
                    updated = await self.env.DB.prepare(
                        "SELECT display_name, academic_year, department FROM users "
                        "WHERE telegram_user_id = ?"
                    ).bind(user_id).first()
                    next_field = next_signup_field(updated) if updated else None
                    if next_field is None:
                        await self._send_message(chat_id, REGISTRATION_COMPLETE, MAIN_MENU)
                    else:
                        await self._send_message(chat_id, signup_prompt(next_field))
                return Response("OK")

            if command == "start":
                # Registration is keyed only by Telegram user ID; the shared
                # plan date is never derived from a user's registration date.
                existing_user = await self.env.DB.prepare(
                    "SELECT display_name, academic_year, department FROM users "
                    "WHERE telegram_user_id = ?"
                ).bind(user_id).first()
                await self.env.DB.prepare(
                    "INSERT INTO users (telegram_user_id, private_chat_id) VALUES (?, ?) "
                    "ON CONFLICT(telegram_user_id) DO UPDATE "
                    "SET private_chat_id = excluded.private_chat_id"
                ).bind(user_id, chat_id).run()
                field = next_signup_field(existing_user) if existing_user is not None else "display_name"
                if field is not None:
                    await self._send_message(chat_id, signup_prompt(field))
                else:
                    await self._send_message(
                        chat_id,
                        REGISTRATION_EXISTING.format(name=existing_user["display_name"]),
                        MAIN_MENU,
                    )
            else:
                user = await self.env.DB.prepare(
                    "SELECT display_name, academic_year, department FROM users "
                    "WHERE telegram_user_id = ?"
                ).bind(user_id).first()
                registered = user is not None and next_signup_field(user) is None
                if registration_required(command, registered):
                    if user is not None:
                        await self._send_message(chat_id, signup_prompt(next_signup_field(user)))
                    else:
                        await self._send_message(chat_id, REGISTRATION_REQUIRED)
                    return Response("OK")

                # Refresh only the private chat destination for a registered
                # user. This does not create an account or change preferences.
                await self.env.DB.prepare(
                    "UPDATE users SET private_chat_id = ? WHERE telegram_user_id = ?"
                ).bind(chat_id, user_id).run()

                current_date = current_eat_date()
                today = current_date.isoformat()
                if command == "today":
                    entry = await self.env.DB.prepare(
                        "SELECT plan_day, ethiopian_date, reading, gregorian_date "
                        "FROM reading_plan WHERE gregorian_date = ?"
                    ).bind(today).first()
                    response_message = format_today_message(entry, current_date)
                    reply_markup = MAIN_MENU
                elif command == "plan":
                    total_row = await self.env.DB.prepare(
                        "SELECT COUNT(*) AS total FROM reading_plan"
                    ).first()
                    total_days = int(total_row["total"]) if total_row else 0
                    page, error = plan_page_for_command(text, total_days)
                    if error:
                        response_message = error
                        reply_markup = MAIN_MENU
                    else:
                        page_size = 14
                        rows = await self.env.DB.prepare(
                            "SELECT plan_day, ethiopian_date, reading, gregorian_date "
                            "FROM reading_plan ORDER BY plan_day LIMIT ? OFFSET ?"
                        ).bind(page_size, (page - 1) * page_size).all()
                        entries = tuple(rows.results) if rows else ()
                        response_message = format_plan_page(entries, page, total_days)
                        reply_markup = plan_page_keyboard(page, total_days, page_size)
                else:
                    stats = await self.env.DB.prepare(
                        "SELECT (SELECT COUNT(*) FROM reading_completions "
                        "WHERE telegram_user_id = ?) AS completed, "
                        "(SELECT COUNT(*) FROM reading_plan) AS total"
                    ).bind(user_id).first()
                    history_rows = await self.env.DB.prepare(
                        "SELECT plan_day FROM reading_completions "
                        "WHERE telegram_user_id = ? ORDER BY plan_day DESC LIMIT 10"
                    ).bind(user_id).all()
                    recent_days = tuple(
                        row["plan_day"] for row in history_rows.results
                    ) if history_rows else ()
                    response_message = format_progress_message(
                        int(stats["completed"]) if stats else 0,
                        int(stats["total"]) if stats else 0,
                        recent_days,
                    )
                    reply_markup = MAIN_MENU
                await self._send_message(chat_id, response_message, reply_markup)

            return Response("OK")

        return Response("Not found", status=404)

    async def _handle_plan_callback(self, callback):
        callback_id = callback.get("id")
        user = callback.get("from") or {}
        message = callback.get("message") or {}
        chat = message.get("chat") or {}
        data = callback.get("data", "")
        if (
            not isinstance(callback_id, str)
            or not isinstance(user.get("id"), int)
            or not isinstance(chat.get("id"), int)
            or chat.get("type") != "private"
            or not isinstance(message.get("message_id"), int)
        ):
            if isinstance(callback_id, str):
                await self._answer_callback(
                    callback_id, "This action is available in a private chat.", True
                )
            return True

        # Telegram requires callback queries to be answered promptly. Do this
        # before D1 lookups so slow database responses cannot expire the query.
        await self._answer_callback(callback_id)

        profile = await self.env.DB.prepare(
            "SELECT display_name, academic_year, department FROM users "
            "WHERE telegram_user_id = ?"
        ).bind(user["id"]).first()
        if profile is None or next_signup_field(profile) is not None:
            return True

        total_row = await self.env.DB.prepare(
            "SELECT COUNT(*) AS total FROM reading_plan"
        ).first()
        total_days = int(total_row["total"]) if total_row else 0
        page_size = 14
        if data.startswith("planpage:"):
            try:
                page = int(data.split(":", 1)[1])
            except ValueError:
                return True
            total_pages = (total_days + page_size - 1) // page_size
            if not 1 <= page <= total_pages:
                return True
            rows = await self.env.DB.prepare(
                "SELECT plan_day, ethiopian_date, reading, gregorian_date "
                "FROM reading_plan ORDER BY plan_day LIMIT ? OFFSET ?"
            ).bind(page_size, (page - 1) * page_size).all()
            entries = tuple(rows.results) if rows else ()
            text = format_plan_page(entries, page, total_days)
            keyboard = plan_page_keyboard(page, total_days, page_size)
        elif data.startswith("plan:"):
            try:
                day = int(data.split(":", 1)[1])
            except ValueError:
                return True
            entry = await self.env.DB.prepare(
                "SELECT plan_day, ethiopian_date, reading, gregorian_date "
                "FROM reading_plan WHERE plan_day = ?"
            ).bind(day).first()
            if entry is None:
                return True
            text = (
                f"Reading Plan · selected day\nDay {entry['plan_day']} · "
                f"{entry['ethiopian_date']} · {entry['gregorian_date']}\n{entry['reading']}"
            )
            keyboard = plan_day_keyboard(day, total_days, page_size)
        else:
            return True

        await self._edit_message(
            chat["id"], message["message_id"], text, keyboard
        )
        return True

    async def _answer_callback(self, callback_id, text="", show_alert=False):
        await self._telegram_request(
            "answerCallbackQuery",
            {"callback_query_id": callback_id, "text": text, "show_alert": show_alert},
        )

    async def _edit_message(self, chat_id, message_id, text, reply_markup):
        await self._telegram_request(
            "editMessageText",
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "reply_markup": reply_markup,
            },
        )

    async def _send_message(self, chat_id: int, text: str, reply_markup: dict | None = None):
        payload = {"chat_id": chat_id, "text": text}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        await self._telegram_request("sendMessage", payload)

    async def _telegram_request(self, method, payload):
        token = getattr(self.env, "TELEGRAM_BOT_TOKEN", "")
        if not token:
            raise RuntimeError("Telegram bot token is not configured")
        options = to_js(
            {
                "method": "POST",
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(payload, ensure_ascii=False),
            },
            dict_converter=Object.fromEntries,
        )
        response = await fetch(
            f"https://api.telegram.org/bot{token}/{method}", options
        )
        result = await response.json()
        if not response.ok or not result.get("ok"):
            # Do not log the token-bearing URL or Telegram's raw response body.
            raise RuntimeError(f"Telegram sendMessage failed with HTTP {response.status}")
