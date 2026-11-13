"""Telegram commands, menu buttons, and per-user callbacks."""

from pathlib import Path
from datetime import time, timedelta
from urllib.parse import urlencode

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InlineQueryResultsButton,
    InputTextMessageContent,
    WebAppInfo,
)
from aiogram.types import Message

from app.database import (
    completed_days,
    completed_reading_history,
    delete_user,
    display_name,
    journal_entry,
    journal_entries,
    mark_read,
    reminders_enabled,
    register_user,
    profile_details,
    leaderboard_entries,
    leaderboard_opt_in,
    signup_stage,
    set_leaderboard_opt_in,
    set_reminders_enabled,
    save_journal_entry,
    user_is_registered,
    update_profile_field,
)
from app.messages import (
    ACCOUNT_DELETED,
    DELETE_ACCOUNT_CANCELLED,
    DELETE_ACCOUNT_PROMPT,
    REGISTRATION_COMPLETE,
    REGISTRATION_EXISTING,
    WELCOME_INTRO,
    REGISTRATION_NAME_PROMPT,
    REGISTRATION_YEAR_PROMPT,
    REGISTRATION_DEPARTMENT_PROMPT,
    PROFILE_EDIT_INVALID,
    PROFILE_EDIT_PROMPT,
    PROFILE_EDIT_SAVED,
)
from app.keyboards import MAIN_MENU
from app.registration import RegistrationGate, registration_prompt_markup
from app.streaks import streak_counts, streak_progress_text
from app.bible import JsonBibleRepository, format_chapter_messages
from app.inline_search import parse_chapter_start_parameter, search_inline
from app.reading_plan import ReadingPlan
from app.references import ReferenceParseError, parse_reading_assignment
from app.readings import (
    PLAN_PAGE_SIZE,
    eat_date,
    entry_for_date,
    format_plan_page,
    format_reading_entry,
    page_for_day,
    plan_page_count,
)


class ProfileEdit(StatesGroup):
    value = State()


class JournalEntryFlow(StatesGroup):
    day = State()
    reference = State()
    reflection = State()
    prayer = State()


def _settings_keyboard(enabled: bool, leaderboard_enabled: bool) -> InlineKeyboardMarkup:
    label = "Turn reminders off" if enabled else "Turn reminders on"
    leaderboard_label = (
        "Leave leaderboard" if leaderboard_enabled else "Join leaderboard"
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data="toggle_reminders")],
        [InlineKeyboardButton(text=leaderboard_label, callback_data="toggle_leaderboard")],
        [InlineKeyboardButton(text="Edit my details", callback_data="profile_edit")],
        [InlineKeyboardButton(text="Delete my account", callback_data="delete_account")],
    ])


def _profile_edit_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Edit name", callback_data="profile_edit:name")],
        [InlineKeyboardButton(text="Edit year of study", callback_data="profile_edit:year")],
        [InlineKeyboardButton(text="Edit department", callback_data="profile_edit:department")],
        [InlineKeyboardButton(text="Cancel", callback_data="profile_edit:cancel")],
    ])


def _settings_text(
    database_path: Path,
    user_id: int,
    enabled: bool,
    leaderboard_enabled: bool,
    delivery_note: str,
) -> str:
    profile = profile_details(database_path, user_id) or {}
    return (
        f"Daily reminders are {'on' if enabled else 'off'}. {delivery_note}\n\n"
        "Your details\n"
        f"Name: {profile.get('name') or 'Not set'}\n"
        f"Year: {profile.get('year') or 'Not set'}\n"
        f"Department: {profile.get('department') or 'Not set'}\n\n"
        "Leaderboard\n"
        + (
            "Your chosen name, study year, and completed-reading count appear. "
            "The same list is shown to everyone who opens it."
            if leaderboard_enabled
            else "You are not listed. Join to share your chosen name, study year, and completed-reading count."
        )
    )

async def _answer_callback(callback: CallbackQuery, *args: object, **kwargs: object) -> None:
    """Acknowledge a button tap, ignoring callbacks Telegram has already expired."""
    try:
        await callback.answer(*args, **kwargs)
    except TelegramBadRequest as error:
        message = str(error).lower()
        if "query is too old" not in message and "query id is invalid" not in message:
            raise


def _read_chapters_button(day: int, mini_app_url: str, in_private_chat: bool) -> InlineKeyboardButton:
    if mini_app_url and in_private_chat:
        return InlineKeyboardButton(
            text="Read Chapters",
            web_app=WebAppInfo(url=f"{mini_app_url}/?{urlencode({'day': day})}"),
        )
    return InlineKeyboardButton(text="Read Chapters", callback_data=f"chapters:{day}")


def _entry_keyboard(day: int, mini_app_url: str, in_private_chat: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Mark as Read", callback_data=f"complete:{day}")],
            [_read_chapters_button(day, mini_app_url, in_private_chat)],
            [InlineKeyboardButton(
                text="View Reading Plan",
                callback_data=f"planpage:{page_for_day(day, PLAN_PAGE_SIZE)}",
            )],
        ]
    )


def _journal_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Write a reflection", callback_data="journal:new")
    ]])


def _plan_keyboard(
    day: int,
    final_day: int,
    mini_app_url: str,
    in_private_chat: bool,
) -> InlineKeyboardMarkup:
    row = []
    if day > 1:
        row.append(InlineKeyboardButton(text="← Previous", callback_data=f"plan:{day - 1}"))
    if day < final_day:
        row.append(InlineKeyboardButton(text="Next →", callback_data=f"plan:{day + 1}"))
    return InlineKeyboardMarkup(
        inline_keyboard=[
            row,
            [InlineKeyboardButton(
                text="All Plan",
                callback_data=f"planpage:{page_for_day(day, PLAN_PAGE_SIZE)}",
            )],
            [
                InlineKeyboardButton(text="Mark as Read", callback_data=f"complete:{day}"),
                _read_chapters_button(day, mini_app_url, in_private_chat),
            ],
        ]
    )


def _overview_keyboard(page: int, total_pages: int, plan: ReadingPlan) -> InlineKeyboardMarkup:
    first_day = (page - 1) * PLAN_PAGE_SIZE + 1
    last_day = min(page * PLAN_PAGE_SIZE, plan.final_day)
    rows = []
    day_buttons = [
        InlineKeyboardButton(text=f"Day {day}", callback_data=f"plan:{day}")
        for day in range(first_day, last_day + 1)
    ]
    rows.extend(day_buttons[index:index + 2] for index in range(0, len(day_buttons), 2))
    navigation = []
    if page > 1:
        navigation.append(InlineKeyboardButton(text="← Previous", callback_data=f"planpage:{page - 1}"))
    if page < total_pages:
        navigation.append(InlineKeyboardButton(text="Next →", callback_data=f"planpage:{page + 1}"))
    if navigation:
        rows.append(navigation)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_router(
    database_path: Path,
    plan: ReadingPlan,
    bible: JsonBibleRepository | None = None,
    mini_app_url: str = "",
    reminder_scheduler_enabled: bool = False,
    reminder_times: tuple[time, ...] | time = (time(6), time(12), time(18)),
) -> Router:
    if isinstance(reminder_times, time):
        reminder_schedule_text = reminder_times.strftime("%H:%M")
    else:
        reminder_schedule_text = ", ".join(slot.strftime("%H:%M") for slot in reminder_times)
    router = Router(name="daily-verse")
    registration_gate = RegistrationGate(database_path)
    router.message.outer_middleware(registration_gate)
    router.callback_query.outer_middleware(registration_gate)

    async def send_today(message: Message) -> None:
        today = eat_date()
        entry = entry_for_date(plan, today)
        if entry is None:
            await message.answer(
                f"There is no scheduled reading for {today.isoformat()} in this plan."
            )
            return
        await message.answer(
            "Today's Reading\n" + format_reading_entry(entry),
            reply_markup=_entry_keyboard(
                entry.day,
                mini_app_url,
                message.chat.type == "private",
            ),
        )

    async def send_plan(message: Message, day: int | None = None) -> None:
        if day is not None and plan.get_day(day) is None:
            await message.answer(f"Choose a plan day from 1 to {plan.final_day}.")
            return
        page = page_for_day(day) if day is not None else 1
        total_pages = plan_page_count(plan)
        await message.answer(
            format_plan_page(plan, page),
            reply_markup=_overview_keyboard(page, total_pages, plan),
        )

    @router.message(Command("start"))
    async def start(message: Message, command: CommandObject) -> None:
        if message.chat.type != "private":
            await message.answer("Please open Daily Verse in a private chat to register.")
            return
        if message.from_user is None:
            return
        is_new_user = register_user(database_path, message.from_user.id, message.chat.id)
        if is_new_user:
            await message.answer(WELCOME_INTRO)
        if not user_is_registered(database_path, message.from_user.id):
            prompts = {
                "name": REGISTRATION_NAME_PROMPT,
                "year": REGISTRATION_YEAR_PROMPT,
                "department": REGISTRATION_DEPARTMENT_PROMPT,
            }
            stage = signup_stage(database_path, message.from_user.id)
            await message.answer(
                prompts.get(stage, REGISTRATION_NAME_PROMPT),
                reply_markup=registration_prompt_markup(stage),
            )
            return
        chapter_reference = parse_chapter_start_parameter(command.args)
        if chapter_reference is not None:
            book_id, chapter_number = chapter_reference
            if bible is None:
                await message.answer("Amharic Bible text is not available right now.")
                return
            chapter = bible.get_chapter(book_id, chapter_number)
            if chapter is None:
                await message.answer("That chapter is not available in the Bible data.")
                return
            if not chapter.complete:
                await message.answer(
                    f"The available source has missing ending text for "
                    f"{chapter.book_name} {chapter.number}; it cannot be shown as a complete chapter."
                )
                return
            for text in format_chapter_messages(chapter):
                await message.answer(text)
            return
        await message.answer(
            REGISTRATION_COMPLETE.format(
                name=display_name(database_path, message.from_user.id) or "friend"
            )
            if is_new_user
            else REGISTRATION_EXISTING.format(
                name=display_name(database_path, message.from_user.id) or "friend"
            ),
            reply_markup=MAIN_MENU,
        )

    @router.inline_query()
    async def bible_inline_search(inline_query: InlineQuery) -> None:
        if not user_is_registered(database_path, inline_query.from_user.id):
            await inline_query.answer(
                [],
                cache_time=0,
                is_personal=True,
                button=InlineQueryResultsButton(
                    text="Open Daily Verse to register",
                    start_parameter="register",
                ),
            )
            return
        response = search_inline(inline_query.query, bible)
        results = [
            InlineQueryResultArticle(
                id=article.id,
                title=article.title,
                description=article.description,
                input_message_content=InputTextMessageContent(
                    message_text=article.message_text,
                ),
            )
            for article in response.articles
        ]
        button = None
        if response.chapter_start_parameter:
            if mini_app_url:
                chapter_reference = parse_chapter_start_parameter(response.chapter_start_parameter)
                if chapter_reference is not None:
                    book_id, chapter_number = chapter_reference
                    mini_app_link = (
                        f"{mini_app_url}/?"
                        f"{urlencode({'book': book_id, 'chapter': chapter_number})}"
                    )
                    button = InlineQueryResultsButton(
                        text="Open full chapter in Daily Verse",
                        web_app=WebAppInfo(url=mini_app_link),
                    )
            if button is None:
                button = InlineQueryResultsButton(
                    text="Open full chapter in Daily Verse",
                    start_parameter=response.chapter_start_parameter,
                )
        await inline_query.answer(
            results,
            cache_time=60,
            is_personal=True,
            button=button,
        )

    @router.message(Command("today"))
    @router.message(F.text == "Today's Reading")
    async def today(message: Message) -> None:
        await send_today(message)

    @router.message(Command("plan"))
    async def plan_command(message: Message, command: CommandObject) -> None:
        requested_day = None
        if command.args:
            try:
                requested_day = int(command.args.strip())
            except ValueError:
                await message.answer("Use /plan followed by a day number, for example /plan 17.")
                return
        await send_plan(message, requested_day)

    @router.message(F.text == "Reading Plan")
    async def plan_button(message: Message) -> None:
        await send_plan(message)

    @router.callback_query(F.data.startswith("planpage:"))
    async def browse_plan_page(callback: CallbackQuery) -> None:
        try:
            page = int(callback.data.split(":", 1)[1])
        except (AttributeError, ValueError):
            await _answer_callback(callback, "That plan page is invalid.", show_alert=True)
            return
        total_pages = plan_page_count(plan)
        if not 1 <= page <= total_pages:
            await _answer_callback(callback, "That page is outside the reading plan.", show_alert=True)
            return
        await _answer_callback(callback)
        if callback.message:
            await callback.message.edit_text(
                format_plan_page(plan, page),
                reply_markup=_overview_keyboard(page, total_pages, plan),
            )

    @router.callback_query(F.data.startswith("plan:"))
    async def browse_plan(callback: CallbackQuery) -> None:
        try:
            day = int(callback.data.split(":", 1)[1])
        except (AttributeError, ValueError):
            await _answer_callback(callback, "That plan day is invalid.", show_alert=True)
            return
        entry = plan.get_day(day)
        if entry is None:
            await _answer_callback(callback, "That day is outside the reading plan.", show_alert=True)
            return
        await _answer_callback(callback)
        if callback.message:
            await callback.message.edit_text(
                "Reading Plan · selected day\n" + format_reading_entry(entry),
                reply_markup=_plan_keyboard(
                    day,
                    plan.final_day,
                    mini_app_url,
                    callback.message.chat.type == "private",
                ),
            )

    @router.callback_query(F.data.startswith("complete:"))
    async def complete_reading(callback: CallbackQuery) -> None:
        if callback.from_user is None:
            await _answer_callback(callback, "Could not identify your Telegram account.", show_alert=True)
            return
        try:
            day = int(callback.data.split(":", 1)[1])
        except (AttributeError, ValueError):
            await _answer_callback(callback, "That plan day is invalid.", show_alert=True)
            return
        if plan.get_day(day) is None:
            await _answer_callback(callback, "That day is outside the reading plan.", show_alert=True)
            return
        inserted = mark_read(database_path, callback.from_user.id, day)
        await _answer_callback(callback, "Marked as read." if inserted else "Already marked as read.")

    @router.callback_query(F.data.startswith("chapters:"))
    async def read_chapters(callback: CallbackQuery) -> None:
        try:
            day = int(callback.data.split(":", 1)[1])
        except (AttributeError, ValueError):
            await _answer_callback(callback, "That plan day is invalid.", show_alert=True)
            return
        entry = plan.get_day(day)
        if entry is None:
            await _answer_callback(callback, "That day is outside the reading plan.", show_alert=True)
            return
        if bible is None:
            await _answer_callback(
                callback,
                "Verified Bible text is not installed yet.", show_alert=True
            )
            return
        try:
            passages = parse_reading_assignment(entry.reading)
        except ReferenceParseError:
            await _answer_callback(
                callback,
                "This reading reference could not be parsed. Please contact an administrator.",
                show_alert=True,
            )
            return
        if callback.message is None:
            await _answer_callback(callback, "Open the bot chat to read chapters.", show_alert=True)
            return
        await _answer_callback(callback, "Sending assigned chapters…")
        for passage in passages:
            chapter = bible.get_chapter(passage.book.id, passage.chapter)
            if chapter is None:
                await callback.message.answer(
                    f"Could not retrieve {passage.book.english} {passage.chapter}. "
                    "No text was substituted."
                )
                continue
            if not chapter.complete:
                await callback.message.answer(
                    f"Could not retrieve the complete text for {passage.book.english} "
                    f"{passage.chapter}. The source data has an empty ending verse slot, "
                    "so this chapter was not displayed as complete."
                )
                continue
            for text in format_chapter_messages(chapter):
                await callback.message.answer(text)

    @router.message(Command("progress"))
    @router.message(F.text == "My Progress")
    async def progress(message: Message) -> None:
        if message.chat.type != "private":
            await message.answer("For privacy, open Daily Verse in a private chat to view progress.")
            return
        if message.from_user is None:
            return
        days = completed_days(database_path, message.from_user.id)
        percentage = (len(days) / plan.total_days * 100) if plan.total_days else 0
        recent = completed_reading_history(database_path, message.from_user.id, limit=5)
        today = eat_date()
        current_entry = entry_for_date(plan, today)
        if current_entry:
            current_plan_day = current_entry.day
        elif today < plan.entries[0].gregorian_date:
            current_plan_day = 0
        elif today <= plan.entries[-1].gregorian_date + timedelta(days=1):
            current_plan_day = plan.final_day
        else:
            current_plan_day = plan.final_day + 2
        current_streak, best_streak = streak_counts(days, current_plan_day)
        history_lines = []
        for day, completed_at in recent:
            entry = plan.get_day(day)
            if entry is not None:
                history_lines.append(
                    f"Day {day} · {completed_at[:10]} — {entry.reading}"
                )
        history_text = "\n".join(history_lines) or "No readings marked complete yet."
        await message.answer(
            f"My Progress\n{streak_progress_text(current_streak, best_streak)}\n\n"
            f"Reading plan: {len(days)} of {plan.total_days} assigned readings marked complete "
            f"({percentage:.1f}%).\n\n"
            "Recent reading plan history\n"
            "These are plan days you marked complete, not whole-Bible coverage.\n"
            f"{history_text}"
        )

    async def send_journal(message: Message) -> None:
        if message.chat.type != "private":
            await message.answer("Your journal is private. Open Daily Verse in a private chat to use it.")
            return
        if message.from_user is None:
            return
        rows = journal_entries(database_path, message.from_user.id, limit=3)
        if not rows:
            text = (
                "My private journal\n\n"
                "Write a reflection or prayer connected to a day in the reading plan. "
                "Only you can view these notes; they are never shown on the leaderboard."
            )
        else:
            sections = [
                "My private journal",
                "Only you can view these notes; they are never shown on the leaderboard.",
            ]
            entry_buttons = []
            for entry_id, day, reference, reflection, _prayer, created_at in rows:
                heading = f"Day {day} · {created_at[:10]}"
                if reference:
                    heading += f" · {reference}"
                section = f"{heading}\n{reflection[:350]}"
                if len(reflection) > 350:
                    section += "…"
                sections.append(section)
                entry_buttons.append([
                    InlineKeyboardButton(
                        text=f"Open Day {day} entry", callback_data=f"journal:view:{entry_id}"
                    )
                ])
            text = "\n\n".join(sections)
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=entry_buttons + [[
                    InlineKeyboardButton(text="Write a reflection", callback_data="journal:new")
                ]]
            )
            await message.answer(text, reply_markup=keyboard)
            return
        await message.answer(text, reply_markup=_journal_keyboard())

    @router.message(Command("journal"))
    @router.message(F.text == "My Journal")
    async def journal_home(message: Message) -> None:
        await send_journal(message)

    @router.callback_query(F.data == "journal:new")
    async def start_journal_entry(callback: CallbackQuery, state: FSMContext) -> None:
        if callback.from_user is None or callback.message is None:
            await _answer_callback(callback, "Could not identify your account.", show_alert=True)
            return
        if callback.message.chat.type != "private":
            await _answer_callback(callback, "Your journal is available only in a private chat.", show_alert=True)
            return
        await state.clear()
        await state.set_state(JournalEntryFlow.day)
        await _answer_callback(callback)
        await callback.message.answer(
            "Which reading-plan day is this for? Send a day number, or type today."
        )

    @router.callback_query(F.data.startswith("journal:view:"))
    async def view_journal_entry(callback: CallbackQuery) -> None:
        if callback.from_user is None or callback.message is None:
            await _answer_callback(callback, "Could not identify your account.", show_alert=True)
            return
        if callback.message.chat.type != "private":
            await _answer_callback(callback, "Journal entries are private.", show_alert=True)
            return
        try:
            entry_id = int((callback.data or "").rsplit(":", 1)[1])
        except (IndexError, ValueError):
            await _answer_callback(callback, "That journal entry is unavailable.", show_alert=True)
            return
        entry = journal_entry(database_path, callback.from_user.id, entry_id)
        if entry is None:
            await _answer_callback(callback, "That journal entry is unavailable.", show_alert=True)
            return
        day, reference, reflection, prayer, created_at = entry
        heading = f"Private journal · Day {day} · {created_at[:10]}"
        if reference:
            heading += f" · {reference}"
        content = f"{heading}\n\n{reflection}"
        if prayer:
            content += f"\n\nPrayer\n{prayer}"
        await _answer_callback(callback)
        await callback.message.answer(content)

    @router.message(Command("cancel"), JournalEntryFlow.day)
    @router.message(Command("cancel"), JournalEntryFlow.reference)
    @router.message(Command("cancel"), JournalEntryFlow.reflection)
    @router.message(Command("cancel"), JournalEntryFlow.prayer)
    async def cancel_journal_entry(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Journal entry cancelled. Nothing was saved.")

    @router.message(JournalEntryFlow.day)
    async def choose_journal_day(message: Message, state: FSMContext) -> None:
        if message.chat.type != "private" or message.from_user is None:
            await message.answer("Your journal is available only in a private chat.")
            return
        value = (message.text or "").strip().casefold()
        if value == "today":
            today_entry = entry_for_date(plan, eat_date())
            day = today_entry.day if today_entry else None
        else:
            try:
                day = int(value)
            except ValueError:
                day = None
        if day is None or plan.get_day(day) is None:
            await message.answer(f"Choose a plan day from 1 to {plan.final_day}, or type today.")
            return
        await state.update_data(journal_day=day)
        await state.set_state(JournalEntryFlow.reference)
        await message.answer(
            f"Day {day}: {plan.get_day(day).reading}\n"
            "Add a verse reference if you want, or type Skip."
        )

    @router.message(JournalEntryFlow.reference)
    async def choose_journal_reference(message: Message, state: FSMContext) -> None:
        reference = (message.text or "").strip()
        if len(reference) > 100:
            await message.answer("Keep the verse reference under 100 characters, or type Skip.")
            return
        await state.update_data(journal_reference=None if reference.casefold() == "skip" else reference)
        await state.set_state(JournalEntryFlow.reflection)
        await message.answer("Write your reflection. It will stay private to your account.")

    @router.message(JournalEntryFlow.reflection)
    async def capture_journal_reflection(message: Message, state: FSMContext) -> None:
        reflection = (message.text or "").strip()
        if not reflection:
            await message.answer("Please send a reflection, or use /cancel to stop without saving.")
            return
        if len(reflection) > 2400:
            await message.answer("Please keep the reflection under 2,400 characters.")
            return
        await state.update_data(journal_reflection=reflection)
        await state.set_state(JournalEntryFlow.prayer)
        await message.answer("Add an optional prayer note, or type Skip to save your reflection.")

    @router.message(JournalEntryFlow.prayer)
    async def save_journal_reflection(message: Message, state: FSMContext) -> None:
        if message.chat.type != "private" or message.from_user is None:
            await state.clear()
            await message.answer("Your journal is available only in a private chat.")
            return
        prayer = (message.text or "").strip()
        if len(prayer) > 900:
            await message.answer("Please keep the optional prayer note under 900 characters, or type Skip.")
            return
        data = await state.get_data()
        save_journal_entry(
            database_path,
            message.from_user.id,
            int(data["journal_day"]),
            str(data["journal_reflection"]),
            data.get("journal_reference"),
            None if prayer.casefold() == "skip" else prayer,
        )
        await state.clear()
        await message.answer(
            "Your private journal entry is saved. Only you can view it.",
            reply_markup=MAIN_MENU,
        )

    @router.message(Command("leaderboard"))
    @router.message(F.text == "Leaderboard")
    async def leaderboard(message: Message) -> None:
        if message.chat.type != "private":
            await message.answer("Open Daily Verse in a private chat to view the leaderboard.")
            return
        rows = leaderboard_entries(database_path)
        if not rows:
            await message.answer(
                "Reading leaderboard\n\nNo readers have joined yet. "
                "Join from Settings to appear here."
            )
            return
        lines = ["Reading leaderboard", "Opted-in readers · completed readings", ""]
        lines.extend(
            f"{rank:02d}  {name}  ·  Year {year}  ·  {count} readings"
            for rank, (_user_id, name, year, count) in enumerate(rows, start=1)
        )
        await message.answer("\n".join(lines))

    @router.message(Command("settings"))
    @router.message(F.text == "Settings")
    async def settings(message: Message) -> None:
        if message.chat.type != "private":
            await message.answer("Open Daily Verse in a private chat to manage your personal settings.")
            return
        if message.from_user is None:
            return
        register_user(
            database_path,
            message.from_user.id,
            message.chat.id if message.chat.type == "private" else None,
        )
        enabled = reminders_enabled(database_path, message.from_user.id)
        opted_in = leaderboard_opt_in(database_path, message.from_user.id)
        delivery_note = (
            f"Reminders are sent at {reminder_schedule_text} EAT, including on days you have marked as read."
            if reminder_scheduler_enabled
            else "Delivery is paused until the hosting scheduler is verified and enabled."
        )
        await message.answer(
            _settings_text(database_path, message.from_user.id, enabled, opted_in, delivery_note),
            reply_markup=_settings_keyboard(enabled, opted_in),
        )

    @router.callback_query(F.data == "toggle_reminders")
    async def toggle_reminders(callback: CallbackQuery) -> None:
        if callback.from_user is None:
            await _answer_callback(callback, "Could not identify your Telegram account.", show_alert=True)
            return
        if callback.message is None or callback.message.chat.type != "private":
            await _answer_callback(callback, "Use this option in a private chat.", show_alert=True)
            return
        register_user(database_path, callback.from_user.id, callback.message.chat.id)
        enabled = not reminders_enabled(database_path, callback.from_user.id)
        set_reminders_enabled(database_path, callback.from_user.id, enabled)
        opted_in = leaderboard_opt_in(database_path, callback.from_user.id)
        await _answer_callback(callback, "Reminders turned on." if enabled else "Reminders turned off.")
        if callback.message:
            delivery_note = (
                f"Reminders are sent at {reminder_schedule_text} EAT, including on days you have marked as read."
                if reminder_scheduler_enabled
                else "Delivery is paused until the hosting scheduler is verified and enabled."
            )
            await callback.message.edit_text(
                _settings_text(database_path, callback.from_user.id, enabled, opted_in, delivery_note),
                reply_markup=_settings_keyboard(enabled, opted_in),
            )

    @router.callback_query(F.data == "toggle_leaderboard")
    async def toggle_leaderboard(callback: CallbackQuery) -> None:
        if callback.from_user is None:
            await _answer_callback(callback, "Could not identify your Telegram account.", show_alert=True)
            return
        if callback.message is None or callback.message.chat.type != "private":
            await _answer_callback(callback, "Use this option in a private chat.", show_alert=True)
            return
        register_user(database_path, callback.from_user.id, callback.message.chat.id)
        opted_in = not leaderboard_opt_in(database_path, callback.from_user.id)
        set_leaderboard_opt_in(database_path, callback.from_user.id, opted_in)
        await _answer_callback(
            callback,
            "You joined the leaderboard." if opted_in else "You left the leaderboard.",
        )
        enabled = reminders_enabled(database_path, callback.from_user.id)
        delivery_note = (
            f"Reminders are sent at {reminder_schedule_text} EAT, including on days you have marked as read."
            if reminder_scheduler_enabled
            else "Delivery is paused until the hosting scheduler is verified and enabled."
        )
        await callback.message.edit_text(
            _settings_text(database_path, callback.from_user.id, enabled, opted_in, delivery_note),
            reply_markup=_settings_keyboard(enabled, opted_in),
        )

    @router.callback_query(F.data.startswith("profile_edit"))
    async def choose_profile_field(callback: CallbackQuery, state: FSMContext) -> None:
        if callback.from_user is None or callback.message is None:
            await _answer_callback(callback, "Could not identify your account.", show_alert=True)
            return
        if callback.message.chat.type != "private":
            await _answer_callback(callback, "Edit your details in a private chat.", show_alert=True)
            return
        data = callback.data or ""
        if data == "profile_edit":
            await _answer_callback(callback)
            await callback.message.edit_text(
                "Which detail would you like to update?",
                reply_markup=_profile_edit_keyboard(),
            )
            return
        action = data.partition(":")[2]
        if action == "cancel":
            await state.clear()
            await _answer_callback(callback)
            await callback.message.edit_text("Edit cancelled. Your details were not changed.")
            return
        if action not in PROFILE_EDIT_PROMPT:
            await _answer_callback(callback, "That profile field is unavailable.", show_alert=True)
            return
        await state.update_data(profile_field=action)
        await state.set_state(ProfileEdit.value)
        await _answer_callback(callback)
        await callback.message.edit_text(
            PROFILE_EDIT_PROMPT[action],
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Cancel", callback_data="profile_edit:cancel")
            ]]),
        )

    @router.message(Command("cancel"), ProfileEdit.value)
    async def cancel_profile_edit(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Edit cancelled. Your details were not changed.")

    @router.message(ProfileEdit.value)
    async def save_profile_edit(message: Message, state: FSMContext) -> None:
        if message.chat.type != "private" or message.from_user is None:
            await message.answer("Please update your details in a private chat.")
            return
        edit_data = await state.get_data()
        field = edit_data.get("profile_field")
        value = message.text or ""
        if field not in PROFILE_EDIT_PROMPT or not update_profile_field(
            database_path, message.from_user.id, field, value
        ):
            await message.answer(PROFILE_EDIT_INVALID.get(field, "That field cannot be updated."))
            return
        await state.clear()
        await message.answer(PROFILE_EDIT_SAVED, reply_markup=MAIN_MENU)

    @router.callback_query(F.data == "delete_account")
    async def request_account_deletion(callback: CallbackQuery) -> None:
        if callback.from_user is None or callback.message is None:
            await _answer_callback(callback, "Could not identify your account.", show_alert=True)
            return
        if callback.message.chat.type != "private":
            await _answer_callback(callback, "Use this option in a private chat.", show_alert=True)
            return
        await _answer_callback(callback)
        await callback.message.edit_text(
            DELETE_ACCOUNT_PROMPT,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Confirm deletion", callback_data="delete_account:confirm")],
                    [InlineKeyboardButton(text="Cancel", callback_data="delete_account:cancel")],
                ]
            ),
        )

    @router.callback_query(F.data == "delete_account:cancel")
    async def cancel_account_deletion(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        if callback.message and callback.message.chat.type == "private":
            await callback.message.edit_text(DELETE_ACCOUNT_CANCELLED)

    @router.callback_query(F.data == "delete_account:confirm")
    async def confirm_account_deletion(callback: CallbackQuery) -> None:
        if callback.from_user is None or callback.message is None:
            await _answer_callback(callback, "Could not identify your account.", show_alert=True)
            return
        if callback.message.chat.type != "private":
            await _answer_callback(callback, "Use this option in a private chat.", show_alert=True)
            return
        await _answer_callback(callback)
        delete_user(database_path, callback.from_user.id)
        await callback.message.edit_text(ACCOUNT_DELETED)

    @router.message(Command("help"))
    @router.message(F.text == "Help")
    async def help_message(message: Message) -> None:
        await message.answer(
            WELCOME_INTRO + "\n\n"
            + "Use /today to see the shared reading, /plan to browse the full plan "
            "or /plan 17 to open the page containing Day 17, "
            "and /progress to see your private completed-plan history. "
            "Use /journal to write a private reflection or prayer for a reading day. "
            "Open Settings to manage reminders or delete your account. "
            "You can mark earlier readings complete from the plan."
        )

    return router
