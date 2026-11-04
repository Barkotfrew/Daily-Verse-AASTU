"""Cloudflare Worker entry point for the incremental hosting migration.

Only private /start and /today messages are implemented. Do not set the
production Telegram webhook until all commands, callbacks, and inline search
have been migrated and tested.
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
    normalize_signup_value,
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

            parts = private_message_parts(update)
            if parts is None:
                return Response("Update type not migrated", status=503)
            user_id, chat_id, text = parts
            command = supported_command(text)
            if command is None:
                user = await self.env.DB.prepare(
                    "SELECT display_name, academic_year, department FROM users "
                    "WHERE telegram_user_id = ?"
                ).bind(user_id).first()
                field = next_signup_field(user) if user is not None else None
                if field is None:
                    return Response("Command not migrated", status=503)
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
                await self._send_message(chat_id, response_message, MAIN_MENU)

            return Response("OK")

        return Response("Not found", status=404)

    async def _send_message(self, chat_id: int, text: str, reply_markup: dict | None = None):
        token = getattr(self.env, "TELEGRAM_BOT_TOKEN", "")
        if not token:
            raise RuntimeError("Telegram bot token is not configured")
        payload = {"chat_id": chat_id, "text": text}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        options = to_js(
            {
                "method": "POST",
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(payload, ensure_ascii=False),
            },
            dict_converter=Object.fromEntries,
        )
        response = await fetch(
            f"https://api.telegram.org/bot{token}/sendMessage", options
        )
        result = await response.json()
        if not response.ok or not result.get("ok"):
            # Do not log the token-bearing URL or Telegram's raw response body.
            raise RuntimeError(f"Telegram sendMessage failed with HTTP {response.status}")
