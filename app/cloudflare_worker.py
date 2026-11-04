"""Cloudflare Worker entry point for the incremental hosting migration.

Private signup, reading-plan browsing, assigned-reading Mini App links, and
bilingual Amharic inline reference search are implemented. Keep the production
webhook on the polling bot until all remaining commands and reminders are tested.
"""

import json
from urllib.parse import urlparse

from workers import Response, WorkerEntrypoint, fetch
from js import Object
from pyodide.ffi import to_js

from app.bible import JsonBibleRepository
from app.inline_search import parse_chapter_start_parameter, search_inline
from app.references import BOOKS, ReferenceParseError, parse_reference
from cloudflare_core import (
    current_eat_date,
    format_progress_message,
    format_today_message,
    format_plan_page,
    mini_app_chapter_asset_url,
    mini_app_reader_keyboard,
    mini_app_reader_url,
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

            inline_query = update.get("inline_query")
            if isinstance(inline_query, dict):
                await self._handle_inline_query(inline_query)
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
                    reply_markup = (
                        self._reader_keyboard(int(entry["plan_day"]))
                        if entry else MAIN_MENU
                    )
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
            reader_keyboard = self._reader_keyboard(day)
            if reader_keyboard:
                keyboard["inline_keyboard"].extend(reader_keyboard["inline_keyboard"])
        else:
            return True

        await self._edit_message(
            chat["id"], message["message_id"], text, keyboard
        )
        return True

    async def _handle_inline_query(self, inline_query):
        query_id = inline_query.get("id")
        user = inline_query.get("from") or {}
        if not isinstance(query_id, str) or not isinstance(user.get("id"), int):
            return

        profile = await self.env.DB.prepare(
            "SELECT display_name, academic_year, department FROM users "
            "WHERE telegram_user_id = ?"
        ).bind(user["id"]).first()
        if profile is None or next_signup_field(profile) is not None:
            await self._telegram_request(
                "answerInlineQuery",
                {
                    "inline_query_id": query_id,
                    "results": [],
                    "cache_time": 0,
                    "is_personal": True,
                    "button": {
                        "text": "Open Daily Verse to register",
                        "start_parameter": "register",
                    },
                },
            )
            return

        query = inline_query.get("query")
        if not isinstance(query, str):
            query = ""
        response = await self._search_inline_from_pages(query)
        result_payload = [
            {
                "type": "article",
                "id": article.id,
                "title": article.title,
                "description": article.description,
                "input_message_content": {"message_text": article.message_text},
            }
            for article in response.articles
        ]
        answer = {
            "inline_query_id": query_id,
            "results": result_payload,
            "cache_time": 30 if query.strip() else 0,
            "is_personal": True,
        }
        if response.chapter_start_parameter:
            chapter_ref = parse_chapter_start_parameter(response.chapter_start_parameter)
            reader_url = (
                self._reader_url(book_id=chapter_ref[0], chapter=chapter_ref[1])
                if chapter_ref else None
            )
            if reader_url:
                answer["button"] = {
                    "text": "Open full chapter in Daily Verse",
                    "web_app": {"url": reader_url},
                }
        await self._telegram_request("answerInlineQuery", answer)

    async def _search_inline_from_pages(self, query):
        # Parsing and result formatting are shared with the polling bot. The
        # Worker fetches only the requested chapter asset from the Pages site.
        empty_repository = JsonBibleRepository.from_payload({"books": []})
        if not query.strip():
            return search_inline(query, empty_repository)
        try:
            reference = parse_reference(query)
        except ReferenceParseError:
            return search_inline(query, empty_repository)
        if reference.chapter_start != reference.chapter_end:
            return search_inline(query, empty_repository)

        repository = await self._fetch_bible_chapter(
            reference.book_id, reference.chapter_start
        )
        return search_inline(query, repository)

    async def _fetch_bible_chapter(self, book_id, chapter_number):
        asset_url = self._chapter_asset_url(book_id, chapter_number)
        if not asset_url:
            return None
        book = next((item for item in BOOKS if item.id == book_id), None)
        if book is None:
            return None
        try:
            response = await fetch(asset_url)
            if not response.ok:
                return None
            chapter = await response.json()
            if (
                not isinstance(chapter, dict)
                or chapter.get("book_id") != book_id
                or chapter.get("number") != chapter_number
                or not isinstance(chapter.get("verses"), list)
            ):
                return None
            return JsonBibleRepository.from_payload({
                "books": [{
                    "id": book_id,
                    "name": chapter.get("book_name") or book.amharic,
                    "chapters": [{
                        "number": chapter_number,
                        "complete": chapter.get("complete", False),
                        "verses": chapter["verses"],
                    }],
                }],
            })
        except Exception:
            # Missing or malformed assets yield a normal unavailable result;
            # never guess text or send an incomplete chapter as complete.
            return None

    def _chapter_asset_url(self, book_id, chapter_number):
        return mini_app_chapter_asset_url(
            getattr(self.env, "MINI_APP_URL", ""), book_id, chapter_number
        )

    def _reader_url(self, day=None, book_id=None, chapter=None):
        return mini_app_reader_url(
            getattr(self.env, "MINI_APP_URL", ""),
            day=day,
            book_id=book_id,
            chapter=chapter,
        )

    def _reader_keyboard(self, day):
        return mini_app_reader_keyboard(
            getattr(self.env, "MINI_APP_URL", ""), day
        )

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
            raise RuntimeError(f"Telegram {method} failed with HTTP {response.status}")
