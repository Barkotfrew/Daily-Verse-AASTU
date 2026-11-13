"""Cloudflare Worker entry point for the Telegram bot and D1-backed features."""

import json
import hashlib
import hmac
import time
from datetime import date
from urllib.parse import parse_qsl, urlparse

from workers import Response, WorkerEntrypoint, fetch

try:
    from app.bible import JsonBibleRepository
    from app.inline_search import parse_chapter_start_parameter, search_inline
    from app.references import BOOKS, ReferenceParseError, parse_reference
    from app.streaks import streak_counts, streak_progress_text
except ModuleNotFoundError as exc:
    # Pywrangler bundles files beside the configured entry point as flat
    # modules, so the local `app` package isn't present in that runtime.
    if exc.name != "app":
        raise
    from bible import JsonBibleRepository
    from inline_search import parse_chapter_start_parameter, search_inline
    from references import BOOKS, ReferenceParseError, parse_reference
    from streaks import streak_counts, streak_progress_text
from cloudflare_core import (
    LEADERBOARD_QUERY,
    current_eat_date,
    completion_button,
    format_progress_message,
    format_leaderboard_message,
    format_today_message,
    format_plan_page,
    mini_app_chapter_asset_url,
    mini_app_reader_keyboard,
    mini_app_reader_url,
    reminder_message,
    reminder_keyboard,
    reminders_settings_message,
    leaderboard_settings_message,
    settings_keyboard,
    profile_edit_keyboard,
    account_delete_keyboard,
    normalize_signup_value,
    plan_page_for_command,
    plan_day_keyboard,
    plan_page_keyboard,
    private_message_parts,
    registration_required,
    scheduled_eat_date,
    supported_command,
    today_keyboard,
    verify_webhook_secret,
)
from messages import (
    ACADEMIC_YEAR_OPTIONS,
    REGISTRATION_COMPLETE,
    REGISTRATION_DEPARTMENT_INVALID,
    REGISTRATION_DEPARTMENT_PROMPT,
    REGISTRATION_EXISTING,
    REGISTRATION_NAME_INVALID,
    REGISTRATION_NAME_PROMPT,
    REGISTRATION_REQUIRED,
    REGISTRATION_YEAR_INVALID,
    REGISTRATION_YEAR_PROMPT,
    WELCOME_INTRO,
)
PROFILE_EDIT_PROMPTS = {
    "display_name": "Send the name you want Daily Verse to use (2–64 characters).",
    "academic_year": "Send your year of study (for example, 2 or 2nd year).",
    "department": "Send your department name (2–80 characters).",
}
PROFILE_EDIT_INVALID = {
    "display_name": "Please send a name using 2 to 64 characters.",
    "academic_year": "Please send your year of study, such as 2 or 2nd year.",
    "department": "Please send a department name between 2 and 80 characters.",
}
DELETE_ACCOUNT_PROMPT = (
    "Delete your Daily Verse account? This also deletes your personal reading progress "
    "and reminder settings. You can register again later with /start."
)


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


def signup_prompt_markup(field):
    if field != "academic_year":
        return {"remove_keyboard": True}
    return {
        "keyboard": [
            list(ACADEMIC_YEAR_OPTIONS[index:index + 2])
            for index in range(0, len(ACADEMIC_YEAR_OPTIONS), 2)
        ],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def format_worker_settings(settings):
    if settings is None:
        return "Settings are unavailable. Please try again."
    return (
        "Your details\n"
        f"Name: {settings['display_name']}\n"
        f"Year: {settings['academic_year']}\n"
        f"Department: {settings['department']}\n\n"
        + reminders_settings_message(bool(settings["reminders_enabled"]))
        + "\n\n"
        + leaderboard_settings_message(bool(settings["leaderboard_opt_in"]))
    )


MAIN_MENU = {
    "keyboard": [
        [{"text": "Today's Reading"}, {"text": "Reading Plan"}],
        [{"text": "My Reading Journey 🌱"}, {"text": "Leaderboard"}],
        [{"text": "Settings"}],
        [{"text": "Help"}],
    ],
    "resize_keyboard": True,
}


class Default(WorkerEntrypoint):
    def _journal_cors_headers(self, request):
        origin = request.headers.get("Origin", "")
        allowed = {
            getattr(self.env, "MINI_APP_URL", "").rstrip("/"),
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        }
        headers = {
            "Vary": "Origin",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
            "Access-Control-Max-Age": "600",
        }
        if origin in allowed and origin:
            headers["Access-Control-Allow-Origin"] = origin
        return headers

    def _journal_response(self, request, payload, status=200):
        headers = self._journal_cors_headers(request)
        headers["Content-Type"] = "application/json; charset=utf-8"
        return Response(json.dumps(payload, ensure_ascii=False), status=status, headers=headers)

    def _mini_app_user_id(self, request):
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("tma "):
            return None
        bot_token = getattr(self.env, "TELEGRAM_BOT_TOKEN", "")
        if not bot_token:
            return None
        raw = authorization[4:]
        if len(raw) > 8192:
            return None
        try:
            pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True)
            if len({key for key, _ in pairs}) != len(pairs):
                return None
            fields = dict(pairs)
            received_hash = fields.pop("hash")
            auth_date = int(fields["auth_date"])
            now = int(time.time())
            if auth_date > now + 60 or now - auth_date > 86400:
                return None
            check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
            secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
            expected_hash = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(received_hash, expected_hash):
                return None
            user = json.loads(fields["user"])
            user_id = user.get("id")
            return user_id if isinstance(user_id, int) and user_id > 0 else None
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    async def _handle_journal_api(self, request, path):
        headers = self._journal_cors_headers(request)
        if request.method == "OPTIONS":
            return Response("", status=204 if "Access-Control-Allow-Origin" in headers else 403, headers=headers)
        if "Access-Control-Allow-Origin" not in headers:
            return self._journal_response(request, {"error": "Origin not allowed"}, 403)
        user_id = self._mini_app_user_id(request)
        if user_id is None:
            return self._journal_response(request, {"error": "Telegram authentication required"}, 401)
        profile = await self.env.DB.prepare(
            "SELECT display_name, academic_year, department FROM users WHERE telegram_user_id = ?"
        ).bind(user_id).first()
        if profile is None or not all(profile[key] for key in ("display_name", "academic_year", "department")):
            return self._journal_response(request, {"error": "Complete bot registration before syncing journals"}, 403)

        if path == "/api/journal" and request.method == "GET":
            result = await self.env.DB.prepare(
                "SELECT COALESCE(client_entry_id, 'bot-' || id) AS client_entry_id, "
                "plan_day, verse_reference, verse_text, reflection, prayer, "
                "created_at, updated_at FROM journal_entries WHERE telegram_user_id = ? "
                "ORDER BY updated_at DESC, id DESC LIMIT 500"
            ).bind(user_id).all()
            rows = tuple(result.results) if result else ()
            entries = [{
                key: row[key] for key in (
                    "client_entry_id", "plan_day", "verse_reference", "verse_text",
                    "reflection", "prayer", "created_at", "updated_at",
                )
            } for row in rows]
            return self._journal_response(request, {"entries": entries})

        entry_id = path.removeprefix("/api/journal/") if path.startswith("/api/journal/") else None
        if request.method == "DELETE" and entry_id:
            await self.env.DB.prepare(
                "DELETE FROM journal_entries WHERE telegram_user_id = ? AND "
                "(client_entry_id = ? OR ('bot-' || id) = ?)"
            ).bind(user_id, entry_id, entry_id).run()
            return self._journal_response(request, {"ok": True})

        if (request.method == "POST" and path == "/api/journal") or (
            request.method == "PUT" and entry_id
        ):
            try:
                body = await request.json()
            except Exception:
                return self._journal_response(request, {"error": "Invalid JSON"}, 400)
            if not isinstance(body, dict):
                return self._journal_response(request, {"error": "Invalid journal entry"}, 400)
            client_entry_id = str(body.get("client_entry_id", entry_id or ""))[:100]
            reference = str(body.get("reference", "Reading reflection")).strip()[:200]
            verse_text = str(body.get("verse_text", "")).strip()[:600]
            reflection = str(body.get("reflection", "")).strip()[:4000]
            prayer = str(body.get("prayer", "")).strip()[:2000]
            plan_day = body.get("plan_day")
            if not client_entry_id or not reference or not (reflection or prayer):
                return self._journal_response(request, {"error": "Entry needs an ID, reference, and reflection or prayer"}, 400)
            if plan_day is not None:
                try:
                    plan_day = int(plan_day)
                except (ValueError, TypeError):
                    return self._journal_response(request, {"error": "Invalid reading day"}, 400)
                valid_day = await self.env.DB.prepare(
                    "SELECT 1 FROM reading_plan WHERE plan_day = ?"
                ).bind(plan_day).first()
                if valid_day is None:
                    plan_day = None
            if request.method == "PUT" and entry_id and entry_id != client_entry_id:
                return self._journal_response(request, {"error": "Entry ID mismatch"}, 400)
            if request.method == "PUT":
                updated = await self.env.DB.prepare(
                    "UPDATE journal_entries SET plan_day = ?, verse_reference = ?, verse_text = ?, "
                    "reflection = ?, prayer = ?, client_entry_id = ?, updated_at = CURRENT_TIMESTAMP "
                    "WHERE telegram_user_id = ? AND "
                    "(client_entry_id = ? OR ('bot-' || id) = ?)"
                ).bind(
                    plan_day, reference, verse_text or None, reflection, prayer or None,
                    client_entry_id, user_id, client_entry_id, client_entry_id,
                ).run()
                meta = getattr(updated, "meta", None)
                changes = getattr(meta, "changes", 0) if meta is not None else 0
                if isinstance(meta, dict):
                    changes = meta.get("changes", changes)
                if not changes:
                    return self._journal_response(request, {"error": "Journal entry not found"}, 404)
            else:
                await self.env.DB.prepare(
                    "INSERT INTO journal_entries (telegram_user_id, plan_day, verse_reference, verse_text, "
                    "reflection, prayer, client_entry_id) VALUES (?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(telegram_user_id, client_entry_id) DO UPDATE SET "
                    "plan_day = excluded.plan_day, verse_reference = excluded.verse_reference, "
                    "verse_text = excluded.verse_text, reflection = excluded.reflection, prayer = excluded.prayer, "
                    "updated_at = CURRENT_TIMESTAMP"
                ).bind(user_id, plan_day, reference, verse_text or None, reflection, prayer or None, client_entry_id).run()
            return self._journal_response(request, {"ok": True, "client_entry_id": client_entry_id})

        return self._journal_response(request, {"error": "Not found"}, 404)

    async def scheduled(self, controller, env, ctx):
        """Queue one bounded subscriber batch for the active 06/12/18 EAT window."""
        if getattr(controller, "cron", "") != "* 3,9,15 * * *":
            return
        timestamp = int(controller.scheduledTime)
        reminder_date = scheduled_eat_date(timestamp)
        from datetime import datetime, timezone

        eat_hour = (datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).hour + 3) % 24
        schedule_slot = f"{eat_hour:02d}:00"
        if schedule_slot not in {"06:00", "12:00", "18:00"}:
            return
        plan = await self.env.DB.prepare(
            "SELECT plan_day, ethiopian_date, gregorian_date, reading "
            "FROM reading_plan WHERE gregorian_date = ?"
        ).bind(reminder_date).first()
        if plan is None:
            return

        await self.env.DB.prepare(
            "INSERT OR IGNORE INTO reminder_runs (reminder_date, schedule_slot) VALUES (?, ?)"
        ).bind(reminder_date, schedule_slot).run()
        run = await self.env.DB.prepare(
            "SELECT last_user_id, finished FROM reminder_runs "
            "WHERE reminder_date = ? AND schedule_slot = ?"
        ).bind(reminder_date, schedule_slot).first()
        if run is None or bool(run["finished"]):
            return
        recipients = await self.env.DB.prepare(
            "SELECT telegram_user_id, private_chat_id FROM users "
            "WHERE reminders_enabled = 1 AND private_chat_id IS NOT NULL "
            "AND display_name IS NOT NULL AND academic_year IS NOT NULL "
            "AND department IS NOT NULL AND telegram_user_id > ? "
            "ORDER BY telegram_user_id LIMIT 100"
        ).bind(run["last_user_id"]).all()
        users = tuple(recipients.results) if recipients else ()
        if not users:
            await self.env.DB.prepare(
                "UPDATE reminder_runs SET finished = 1 "
                "WHERE reminder_date = ? AND schedule_slot = ?"
            ).bind(reminder_date, schedule_slot).run()
            return

        insert_statements = [
            self.env.DB.prepare(
                "INSERT OR IGNORE INTO reminder_deliveries "
                "(reminder_date, schedule_slot, telegram_user_id, plan_day, status) "
                "VALUES (?, ?, ?, ?, 'queued')"
            ).bind(reminder_date, schedule_slot, user["telegram_user_id"], plan["plan_day"])
            for user in users
        ]
        await self.env.DB.batch(insert_statements)
        message = reminder_message(
            int(plan["plan_day"]), plan["ethiopian_date"],
            plan["gregorian_date"], plan["reading"],
        )
        batch = [
            {"body": {
                "reminder_date": reminder_date,
                "schedule_slot": schedule_slot,
                "telegram_user_id": int(user["telegram_user_id"]),
                "chat_id": int(user["private_chat_id"]),
                "text": message,
                "reply_markup": reminder_keyboard(
                    getattr(self.env, "MINI_APP_URL", ""), int(plan["plan_day"])
                ),
            }}
            for user in users
        ]
        await self.env.REMINDER_QUEUE.sendBatch(batch)
        await self.env.DB.prepare(
            "UPDATE reminder_runs SET last_user_id = ? "
            "WHERE reminder_date = ? AND schedule_slot = ?"
        ).bind(users[-1]["telegram_user_id"], reminder_date, schedule_slot).run()

    async def queue(self, batch):
        """Deliver queued reminders independently and retry transient failures."""
        for message in batch.messages:
            body = message.body
            try:
                if not isinstance(body, dict):
                    message.ack()
                    continue
                reminder_date = body.get("reminder_date")
                schedule_slot = body.get("schedule_slot")
                user_id = body.get("telegram_user_id")
                chat_id = body.get("chat_id")
                text = body.get("text")
                if (
                    not isinstance(reminder_date, str)
                    or schedule_slot not in {"06:00", "12:00", "18:00"}
                    or not isinstance(user_id, int)
                    or not isinstance(chat_id, int)
                    or not isinstance(text, str)
                ):
                    message.ack()
                    continue

                # Claim atomically before calling Telegram. A repeated queue
                # delivery cannot send again after a successful send/restart.
                claim = await self.env.DB.prepare(
                    "UPDATE reminder_deliveries SET status = 'sent', "
                    "attempts = attempts + 1, last_error = NULL "
                    "WHERE reminder_date = ? AND telegram_user_id = ? "
                    "AND schedule_slot = ? "
                    "AND status IN ('queued', 'failed') "
                    "AND EXISTS (SELECT 1 FROM users WHERE telegram_user_id = ? "
                    "AND reminders_enabled = 1 AND private_chat_id = ?)"
                ).bind(reminder_date, user_id, schedule_slot, user_id, chat_id).run()
                meta = getattr(claim, "meta", None)
                if meta is None and isinstance(claim, dict):
                    meta = claim.get("meta")
                changes = getattr(meta, "changes", 0) if meta is not None else 0
                if isinstance(meta, dict):
                    changes = meta.get("changes", changes)
                if not changes:
                    message.ack()
                    continue

                try:
                    await self._telegram_request(
                        "sendMessage", {
                            "chat_id": chat_id,
                            "text": text,
                            "reply_markup": body.get("reply_markup"),
                        }
                    )
                except Exception:
                    await self.env.DB.prepare(
                        "UPDATE reminder_deliveries SET status = 'failed', "
                        "last_error = 'Telegram delivery failed' "
                        "WHERE reminder_date = ? AND telegram_user_id = ? "
                        "AND schedule_slot = ? "
                        "AND status = 'sent'"
                    ).bind(reminder_date, user_id, schedule_slot).run()
                    if int(getattr(message, "attempts", 1)) < 5:
                        message.retry(delaySeconds=120)
                    else:
                        message.ack()
                    continue
                message.ack()
            except Exception:
                # One malformed or failed item must not stop other recipients.
                try:
                    message.retry(delaySeconds=120)
                except Exception:
                    message.ack()

    async def fetch(self, request):
        path = urlparse(request.url).path

        if path == "/api/journal" or path.startswith("/api/journal/"):
            return await self._handle_journal_api(request, path)

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
            pending = await self.env.DB.prepare(
                "SELECT pending_profile_field FROM users WHERE telegram_user_id = ?"
            ).bind(user_id).first()
            pending_field = pending["pending_profile_field"] if pending else None
            if pending_field:
                if text.strip().lower() in {"/cancel", "cancel"}:
                    await self.env.DB.prepare(
                        "UPDATE users SET pending_profile_field = NULL WHERE telegram_user_id = ?"
                    ).bind(user_id).run()
                    await self._send_message(
                        chat_id, "Edit cancelled. Your details were not changed.", MAIN_MENU
                    )
                    return Response("OK")
                minimum, maximum = {
                    "display_name": (2, 64),
                    "academic_year": (1, 24),
                    "department": (2, 80),
                }[pending_field]
                value = normalize_signup_value(text, minimum, maximum)
                if value is None:
                    await self._send_message(chat_id, PROFILE_EDIT_INVALID[pending_field])
                else:
                    await self.env.DB.prepare(
                        f"UPDATE users SET {pending_field} = ?, pending_profile_field = NULL "
                        "WHERE telegram_user_id = ?"
                    ).bind(value, user_id).run()
                    await self._send_message(
                        chat_id, "Your details have been updated.", MAIN_MENU
                    )
                return Response("OK")
            draft = await self.env.DB.prepare(
                "SELECT stage, plan_day FROM journal_drafts WHERE telegram_user_id = ?"
            ).bind(user_id).first()
            if draft is not None:
                stripped = text.strip()
                if stripped.casefold() in {"/cancel", "cancel"}:
                    await self.env.DB.prepare(
                        "DELETE FROM journal_drafts WHERE telegram_user_id = ?"
                    ).bind(user_id).run()
                    await self._send_message(chat_id, "Journal entry cancelled. Nothing was saved.", MAIN_MENU)
                    return Response("OK")
                stage = draft["stage"]
                if stage == "day":
                    if stripped.casefold() == "today":
                        selected = await self.env.DB.prepare(
                            "SELECT plan_day FROM reading_plan WHERE gregorian_date = ?"
                        ).bind(current_eat_date().isoformat()).first()
                        day = int(selected["plan_day"]) if selected else None
                    else:
                        try:
                            day = int(stripped)
                        except ValueError:
                            day = None
                    valid_day = await self.env.DB.prepare(
                        "SELECT plan_day FROM reading_plan WHERE plan_day = ?"
                    ).bind(day).first() if day is not None else None
                    if valid_day is None:
                        bounds = await self.env.DB.prepare(
                            "SELECT MIN(plan_day) AS first_day, MAX(plan_day) AS last_day FROM reading_plan"
                        ).first()
                        await self._send_message(
                            chat_id,
                            f"Choose a plan day from {bounds['first_day']} to {bounds['last_day']}, or type today."
                            if bounds else "The reading plan is unavailable right now.",
                        )
                    else:
                        await self.env.DB.prepare(
                            "UPDATE journal_drafts SET plan_day = ?, stage = 'reference' "
                            "WHERE telegram_user_id = ?"
                        ).bind(day, user_id).run()
                        await self._send_message(chat_id, "Add a verse reference, or type Skip.")
                elif stage == "reference":
                    if len(stripped) > 100:
                        await self._send_message(chat_id, "Keep the verse reference under 100 characters, or type Skip.")
                    else:
                        reference = None if stripped.casefold() == "skip" else stripped
                        await self.env.DB.prepare(
                            "UPDATE journal_drafts SET verse_reference = ?, stage = 'reflection' "
                            "WHERE telegram_user_id = ?"
                        ).bind(reference, user_id).run()
                        await self._send_message(chat_id, "Write your reflection. It will stay private to your account.")
                elif stage == "reflection":
                    if not stripped:
                        await self._send_message(chat_id, "Please send a reflection, or use /cancel to stop without saving.")
                    elif len(stripped) > 2400:
                        await self._send_message(chat_id, "Please keep the reflection under 2,400 characters.")
                    else:
                        await self.env.DB.prepare(
                            "UPDATE journal_drafts SET reflection = ?, stage = 'prayer' "
                            "WHERE telegram_user_id = ?"
                        ).bind(stripped, user_id).run()
                        await self._send_message(chat_id, "Add an optional prayer note, or type Skip to save your reflection.")
                else:
                    if len(stripped) > 900:
                        await self._send_message(chat_id, "Please keep the optional prayer note under 900 characters, or type Skip.")
                    else:
                        prayer = None if stripped.casefold() == "skip" else stripped
                        await self.env.DB.prepare(
                            "INSERT INTO journal_entries "
                            "(telegram_user_id, plan_day, verse_reference, reflection, prayer) "
                            "SELECT telegram_user_id, plan_day, verse_reference, reflection, ? "
                            "FROM journal_drafts WHERE telegram_user_id = ?"
                        ).bind(prayer, user_id).run()
                        await self.env.DB.prepare(
                            "DELETE FROM journal_drafts WHERE telegram_user_id = ?"
                        ).bind(user_id).run()
                        await self._send_message(
                            chat_id, "Your private journal entry is saved. Only you can view it.", MAIN_MENU
                        )
                return Response("OK")
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
                if field == "academic_year" and value not in ACADEMIC_YEAR_OPTIONS:
                    value = None
                if value is None:
                    await self._send_message(chat_id, invalid, signup_prompt_markup(field))
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
                        await self._send_message(
                            chat_id,
                            REGISTRATION_COMPLETE.format(
                                name=(updated.get("display_name") if updated else None) or "friend"
                            ),
                            MAIN_MENU,
                        )
                    else:
                        await self._send_message(
                            chat_id, signup_prompt(next_field), signup_prompt_markup(next_field)
                        )
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
                if existing_user is None:
                    await self._send_message(chat_id, WELCOME_INTRO)
                if field is not None:
                    await self._send_message(
                        chat_id, signup_prompt(field), signup_prompt_markup(field)
                    )
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
                        field = next_signup_field(user)
                        await self._send_message(
                            chat_id, signup_prompt(field), signup_prompt_markup(field)
                        )
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
                    if entry:
                        completed = await self.env.DB.prepare(
                            "SELECT 1 AS completed FROM reading_completions "
                            "WHERE telegram_user_id = ? AND plan_day = ?"
                        ).bind(user_id, entry["plan_day"]).first()
                        reply_markup = today_keyboard(
                            getattr(self.env, "MINI_APP_URL", ""),
                            int(entry["plan_day"]),
                            completed is not None,
                        )
                    else:
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
                elif command == "settings":
                    settings = await self.env.DB.prepare(
                        "SELECT display_name, academic_year, department, reminders_enabled, "
                        "leaderboard_opt_in FROM users "
                        "WHERE telegram_user_id = ?"
                    ).bind(user_id).first()
                    enabled = bool(settings["reminders_enabled"]) if settings else False
                    leaderboard_enabled = bool(settings["leaderboard_opt_in"]) if settings else False
                    response_message = format_worker_settings(settings)
                    reply_markup = settings_keyboard(enabled, leaderboard_enabled)
                elif command == "journal":
                    entries_result = await self.env.DB.prepare(
                        "SELECT id, plan_day, verse_reference, reflection, created_at "
                        "FROM journal_entries WHERE telegram_user_id = ? "
                        "ORDER BY created_at DESC, id DESC LIMIT 5"
                    ).bind(user_id).all()
                    entries = tuple(entries_result.results) if entries_result else ()
                    if not entries:
                        response_message = (
                            "My private journal\n\n"
                            "Write a reflection or prayer connected to a reading-plan day. "
                            "Only you can view these notes; they are never shown on the leaderboard."
                        )
                    else:
                        sections = [
                            "My private journal",
                            "Only you can view these notes; they are never shown on the leaderboard.",
                        ]
                        entry_buttons = []
                        for item in entries:
                            heading = (
                                f"Day {item['plan_day']} · {str(item['created_at'])[:10]}"
                                if item["plan_day"] is not None
                                else f"{str(item['created_at'])[:10]}"
                            )
                            if item["verse_reference"]:
                                heading += f" · {item['verse_reference']}"
                            preview = str(item["reflection"])
                            sections.append(heading + "\n" + preview[:250] + ("…" if len(preview) > 250 else ""))
                            entry_buttons.append([{
                                "text": f"Open Day {item['plan_day']} entry" if item["plan_day"] is not None else "Open journal entry",
                                "callback_data": f"journal:view:{item['id']}",
                            }])
                        response_message = "\n\n".join(sections)
                        reply_markup = {"inline_keyboard": entry_buttons + [[{
                            "text": "Write a reflection", "callback_data": "journal:new"
                        }]]}
                        await self._send_message(chat_id, response_message, reply_markup)
                        return Response("OK")
                    reply_markup = {"inline_keyboard": [[{
                        "text": "Write a reflection", "callback_data": "journal:new"
                    }]]}
                elif command == "leaderboard":
                    result = await self.env.DB.prepare(LEADERBOARD_QUERY).all()
                    rows = tuple(result.results) if result else ()
                    response_message = format_leaderboard_message(rows)
                    reply_markup = MAIN_MENU
                elif command == "help":
                    response_message = (
                        WELCOME_INTRO + "\n\n"
                        + "Use /today to see today's assigned reading, /plan to browse "
                        "the full plan, or /plan 17 to open the page containing Day 17. "
                        "Open a plan day to read its chapters and mark it complete. "
                        "Use /progress to see your reading journey and streak, "
                        "/leaderboard to view readers who opted in, and /settings to manage "
                        "reminders and leaderboard privacy. Open the Mini App for private journaling."
                    )
                    reply_markup = MAIN_MENU
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
                    all_rows = await self.env.DB.prepare(
                        "SELECT plan_day FROM reading_completions "
                        "WHERE telegram_user_id = ? ORDER BY plan_day"
                    ).bind(user_id).all()
                    completed_days = tuple(
                        int(row["plan_day"]) for row in all_rows.results
                    ) if all_rows else ()
                    scheduled_today = await self.env.DB.prepare(
                        "SELECT plan_day FROM reading_plan WHERE gregorian_date = ?"
                    ).bind(today).first()
                    if scheduled_today:
                        current_plan_day = int(scheduled_today["plan_day"])
                    else:
                        latest_plan_day = await self.env.DB.prepare(
                            "SELECT plan_day, gregorian_date FROM reading_plan "
                            "WHERE gregorian_date < ? ORDER BY plan_day DESC LIMIT 1"
                        ).bind(today).first()
                        current_plan_day = (
                            int(latest_plan_day["plan_day"])
                            + (current_date - date.fromisoformat(latest_plan_day["gregorian_date"])).days
                            if latest_plan_day
                            else 0
                        )
                    current_streak, best_streak = streak_counts(
                        completed_days, current_plan_day
                    )
                    response_message = format_progress_message(
                        int(stats["completed"]) if stats else 0,
                        int(stats["total"]) if stats else 0,
                        recent_days,
                        streak=streak_progress_text(current_streak, best_streak),
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

        if data == "journal:new":
            await self.env.DB.prepare(
                "INSERT INTO journal_drafts (telegram_user_id, stage) VALUES (?, 'day') "
                "ON CONFLICT(telegram_user_id) DO UPDATE SET stage = 'day', plan_day = NULL, "
                "verse_reference = NULL, reflection = NULL, created_at = CURRENT_TIMESTAMP"
            ).bind(user["id"]).run()
            await self._send_message(
                chat["id"],
                "Which reading-plan day is this for? Send a day number, or type today.\n"
                "Send /cancel at any time to discard the entry.",
            )
            return True

        if data.startswith("journal:view:"):
            try:
                entry_id = int(data.rsplit(":", 1)[1])
            except ValueError:
                return True
            entry = await self.env.DB.prepare(
                "SELECT plan_day, verse_reference, reflection, prayer, created_at "
                "FROM journal_entries WHERE telegram_user_id = ? AND id = ?"
            ).bind(user["id"], entry_id).first()
            if entry is None:
                await self._send_message(chat["id"], "That journal entry is unavailable.")
                return True
            heading = f"Private journal · Day {entry['plan_day']} · {str(entry['created_at'])[:10]}"
            if entry["verse_reference"]:
                heading += f" · {entry['verse_reference']}"
            text = heading + "\n\n" + str(entry["reflection"])
            if entry["prayer"]:
                text += "\n\nPrayer\n" + str(entry["prayer"])
            await self._send_message(chat["id"], text)
            return True

        profile = await self.env.DB.prepare(
            "SELECT display_name, academic_year, department, reminders_enabled, "
            "leaderboard_opt_in, pending_profile_field FROM users "
            "WHERE telegram_user_id = ?"
        ).bind(user["id"]).first()
        if profile is None or next_signup_field(profile) is not None:
            return True

        if data == "profile:edit":
            await self._edit_message(
                chat["id"], message["message_id"],
                "Which detail would you like to update?", profile_edit_keyboard(),
            )
            return True

        if data.startswith("profile:field:"):
            field = data.rsplit(":", 1)[-1]
            if field not in PROFILE_EDIT_PROMPTS:
                return True
            await self.env.DB.prepare(
                "UPDATE users SET pending_profile_field = ? WHERE telegram_user_id = ?"
            ).bind(field, user["id"]).run()
            await self._edit_message(
                chat["id"], message["message_id"],
                PROFILE_EDIT_PROMPTS[field] + "\nSend /cancel to stop.",
                {"inline_keyboard": [[{"text": "Cancel", "callback_data": "profile:cancel"}]]},
            )
            return True

        if data == "profile:cancel":
            await self.env.DB.prepare(
                "UPDATE users SET pending_profile_field = NULL WHERE telegram_user_id = ?"
            ).bind(user["id"]).run()
            await self._edit_message(
                chat["id"], message["message_id"],
                "Edit cancelled. Your details were not changed.", MAIN_MENU,
            )
            return True

        if data == "account:delete":
            await self._edit_message(
                chat["id"], message["message_id"],
                DELETE_ACCOUNT_PROMPT,
                account_delete_keyboard(),
            )
            return True

        if data == "account:cancel":
            await self._edit_message(
                chat["id"], message["message_id"],
                "Account deletion cancelled. Your account and progress are unchanged.",
                MAIN_MENU,
            )
            return True

        if data == "account:confirm":
            await self.env.DB.prepare(
                "DELETE FROM users WHERE telegram_user_id = ?"
            ).bind(user["id"]).run()
            await self._edit_message(
                chat["id"], message["message_id"],
                "Your account and personal records have been deleted. Send /start to register again.",
                {"inline_keyboard": []},
            )
            return True

        if data == "reminders:toggle":
            await self.env.DB.prepare(
                "UPDATE users SET reminders_enabled = 1 - reminders_enabled "
                "WHERE telegram_user_id = ?"
            ).bind(user["id"]).run()
            settings = await self.env.DB.prepare(
                "SELECT display_name, academic_year, department, reminders_enabled, "
                "leaderboard_opt_in FROM users "
                "WHERE telegram_user_id = ?"
            ).bind(user["id"]).first()
            enabled = bool(settings["reminders_enabled"]) if settings else False
            leaderboard_enabled = bool(settings["leaderboard_opt_in"]) if settings else False
            await self._edit_message(
                chat["id"], message["message_id"],
                format_worker_settings(settings),
                settings_keyboard(enabled, leaderboard_enabled),
            )
            return True

        if data == "leaderboard:toggle":
            await self.env.DB.prepare(
                "UPDATE users SET leaderboard_opt_in = 1 - leaderboard_opt_in "
                "WHERE telegram_user_id = ?"
            ).bind(user["id"]).run()
            settings = await self.env.DB.prepare(
                "SELECT display_name, academic_year, department, reminders_enabled, "
                "leaderboard_opt_in FROM users "
                "WHERE telegram_user_id = ?"
            ).bind(user["id"]).first()
            reminders_on = bool(settings["reminders_enabled"]) if settings else False
            leaderboard_on = bool(settings["leaderboard_opt_in"]) if settings else False
            await self._edit_message(
                chat["id"], message["message_id"],
                format_worker_settings(settings),
                settings_keyboard(reminders_on, leaderboard_on),
            )
            return True

        is_plan_completion = data.startswith("plancomplete:")
        if data.startswith("complete:") or is_plan_completion:
            try:
                day = int(data.split(":", 1)[1])
            except ValueError:
                return True
            entry = await self.env.DB.prepare(
                "SELECT plan_day FROM reading_plan WHERE plan_day = ?"
            ).bind(day).first()
            if entry is None:
                return True
            await self.env.DB.prepare(
                "INSERT OR IGNORE INTO reading_completions "
                "(telegram_user_id, plan_day) VALUES (?, ?)"
            ).bind(user["id"], day).run()
            if is_plan_completion:
                plan_total = await self.env.DB.prepare(
                    "SELECT COUNT(*) AS total FROM reading_plan"
                ).first()
                total_days = int(plan_total["total"]) if plan_total else 0
                keyboard = plan_day_keyboard(day, total_days)
                keyboard["inline_keyboard"].append(
                    completion_button(day, True, "plancomplete")
                )
                reader_keyboard = self._reader_keyboard(day)
                if reader_keyboard:
                    keyboard["inline_keyboard"].extend(reader_keyboard["inline_keyboard"])
            else:
                keyboard = today_keyboard(
                    getattr(self.env, "MINI_APP_URL", ""), day, completed=True
                )
            await self._edit_reply_markup(chat["id"], message["message_id"], keyboard)
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
            completion = await self.env.DB.prepare(
                "SELECT 1 AS completed FROM reading_completions "
                "WHERE telegram_user_id = ? AND plan_day = ?"
            ).bind(user["id"], day).first()
            keyboard["inline_keyboard"].append(
                completion_button(day, completion is not None, "plancomplete")
            )
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

    async def _edit_reply_markup(self, chat_id, message_id, reply_markup):
        await self._telegram_request(
            "editMessageReplyMarkup",
            {"chat_id": chat_id, "message_id": message_id,
             "reply_markup": reply_markup},
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
        response = await fetch(
            f"https://api.telegram.org/bot{token}/{method}",
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps(payload, ensure_ascii=False),
        )
        result = await response.json()
        if not response.ok or not result.get("ok"):
            # Do not log the token-bearing URL or Telegram's raw response body.
            raise RuntimeError(f"Telegram {method} failed with HTTP {response.status}")
