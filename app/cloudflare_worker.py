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
    format_today_message,
    normalize_display_name,
    private_message_parts,
    registration_required,
    supported_command,
    verify_webhook_secret,
)
from messages import REGISTRATION_COMPLETE, REGISTRATION_EXISTING, REGISTRATION_REQUIRED

REGISTRATION_NAME_PROMPT = (
    "What name or username should we show for you?\n"
    "A nickname is fine. It may appear on a future reading leaderboard."
)
REGISTRATION_NAME_INVALID = "Please send a name or nickname between 2 and 32 characters."


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
                    "SELECT display_name FROM users WHERE telegram_user_id = ?"
                ).bind(user_id).first()
                if user is None or user["display_name"]:
                    return Response("Command not migrated", status=503)
                name = normalize_display_name(text)
                if name is None:
                    await self._send_message(chat_id, REGISTRATION_NAME_INVALID)
                else:
                    await self.env.DB.prepare(
                        "UPDATE users SET display_name = ?, private_chat_id = ? "
                        "WHERE telegram_user_id = ? AND display_name IS NULL"
                    ).bind(name, chat_id, user_id).run()
                    await self._send_message(chat_id, REGISTRATION_COMPLETE, MAIN_MENU)
                return Response("OK")

            if command == "start":
                # Registration is keyed only by Telegram user ID; the shared
                # plan date is never derived from a user's registration date.
                existing_user = await self.env.DB.prepare(
                    "SELECT display_name FROM users WHERE telegram_user_id = ?"
                ).bind(user_id).first()
                await self.env.DB.prepare(
                    "INSERT INTO users (telegram_user_id, private_chat_id) VALUES (?, ?) "
                    "ON CONFLICT(telegram_user_id) DO UPDATE "
                    "SET private_chat_id = excluded.private_chat_id"
                ).bind(user_id, chat_id).run()
                if existing_user is None or not existing_user["display_name"]:
                    await self._send_message(chat_id, REGISTRATION_NAME_PROMPT)
                else:
                    await self._send_message(
                        chat_id,
                        REGISTRATION_EXISTING.format(name=existing_user["display_name"]),
                        MAIN_MENU,
                    )
            else:
                user = await self.env.DB.prepare(
                    "SELECT display_name FROM users WHERE telegram_user_id = ?"
                ).bind(user_id).first()
                registered = bool(user and user["display_name"])
                if registration_required(command, registered):
                    if user is not None:
                        await self._send_message(chat_id, REGISTRATION_NAME_PROMPT)
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
                entry = await self.env.DB.prepare(
                    "SELECT plan_day, ethiopian_date, reading, gregorian_date "
                    "FROM reading_plan WHERE gregorian_date = ?"
                ).bind(today).first()
                await self._send_message(
                    chat_id, format_today_message(entry, current_date), MAIN_MENU
                )

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
