"""Telegram commands, menu buttons, and per-user callbacks."""

from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from app.database import (
    completed_days,
    mark_read,
    reminders_enabled,
    register_user,
    set_reminders_enabled,
)
from app.reading_plan import ReadingPlan
from app.readings import (
    PLAN_PAGE_SIZE,
    eat_date,
    entry_for_date,
    format_plan_page,
    format_reading_entry,
    page_for_day,
    plan_page_count,
)

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Today's Reading"), KeyboardButton(text="Reading Plan")],
        [KeyboardButton(text="My Progress"), KeyboardButton(text="Settings")],
        [KeyboardButton(text="Help")],
    ],
    resize_keyboard=True,
)


def _entry_keyboard(day: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Mark as Read", callback_data=f"complete:{day}")],
            [InlineKeyboardButton(text="Read Chapters", callback_data=f"chapters:{day}")],
            [InlineKeyboardButton(
                text="View Reading Plan",
                callback_data=f"planpage:{page_for_day(day, PLAN_PAGE_SIZE)}",
            )],
        ]
    )


def _plan_keyboard(day: int, final_day: int) -> InlineKeyboardMarkup:
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
                InlineKeyboardButton(text="Read Chapters", callback_data=f"chapters:{day}"),
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


def build_router(database_path: Path, plan: ReadingPlan) -> Router:
    router = Router(name="daily-verse")

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
            reply_markup=_entry_keyboard(entry.day),
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
    async def start(message: Message) -> None:
        if message.from_user is not None:
            register_user(database_path, message.from_user.id)
        await message.answer(
            "ሰላም ተወዳጆች እንዴት ናችሁ? 👋👋👋\n"
            "Welcome to Daily Verse. Choose an option below.",
            reply_markup=MAIN_MENU,
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
            await callback.answer("That plan page is invalid.", show_alert=True)
            return
        total_pages = plan_page_count(plan)
        if not 1 <= page <= total_pages:
            await callback.answer("That page is outside the reading plan.", show_alert=True)
            return
        if callback.message:
            await callback.message.edit_text(
                format_plan_page(plan, page),
                reply_markup=_overview_keyboard(page, total_pages, plan),
            )
        await callback.answer()

    @router.callback_query(F.data.startswith("plan:"))
    async def browse_plan(callback: CallbackQuery) -> None:
        try:
            day = int(callback.data.split(":", 1)[1])
        except (AttributeError, ValueError):
            await callback.answer("That plan day is invalid.", show_alert=True)
            return
        entry = plan.get_day(day)
        if entry is None:
            await callback.answer("That day is outside the reading plan.", show_alert=True)
            return
        if callback.message:
            await callback.message.edit_text(
                "Reading Plan · selected day\n" + format_reading_entry(entry),
                reply_markup=_plan_keyboard(day, plan.final_day),
            )
        await callback.answer()

    @router.callback_query(F.data.startswith("complete:"))
    async def complete_reading(callback: CallbackQuery) -> None:
        if callback.from_user is None:
            await callback.answer("Could not identify your Telegram account.", show_alert=True)
            return
        try:
            day = int(callback.data.split(":", 1)[1])
        except (AttributeError, ValueError):
            await callback.answer("That plan day is invalid.", show_alert=True)
            return
        if plan.get_day(day) is None:
            await callback.answer("That day is outside the reading plan.", show_alert=True)
            return
        inserted = mark_read(database_path, callback.from_user.id, day)
        await callback.answer("Marked as read." if inserted else "Already marked as read.")

    @router.callback_query(F.data.startswith("chapters:"))
    async def read_chapters(callback: CallbackQuery) -> None:
        try:
            day = int(callback.data.split(":", 1)[1])
        except (AttributeError, ValueError):
            await callback.answer("That plan day is invalid.", show_alert=True)
            return
        entry = plan.get_day(day)
        if entry is None:
            await callback.answer("That day is outside the reading plan.", show_alert=True)
            return
        await callback.answer(
            f"Bible text for {entry.reading} is not connected yet.", show_alert=True
        )

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
        history = ", ".join(str(day) for day in days[-10:]) or "None yet"
        await message.answer(
            f"My Progress\n{len(days)} of {plan.total_days} readings completed "
            f"({percentage:.1f}%).\nRecent completed days: {history}"
        )

    @router.message(Command("settings"))
    @router.message(F.text == "Settings")
    async def settings(message: Message) -> None:
        if message.from_user is None:
            return
        enabled = reminders_enabled(database_path, message.from_user.id)
        label = "Turn reminders off" if enabled else "Turn reminders on"
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=label, callback_data="toggle_reminders")]]
        )
        status = "on" if enabled else "off"
        await message.answer(
            f"Daily reminders are {status}. Reminder delivery will be available when scheduling is connected.",
            reply_markup=keyboard,
        )

    @router.callback_query(F.data == "toggle_reminders")
    async def toggle_reminders(callback: CallbackQuery) -> None:
        if callback.from_user is None:
            await callback.answer("Could not identify your Telegram account.", show_alert=True)
            return
        enabled = not reminders_enabled(database_path, callback.from_user.id)
        set_reminders_enabled(database_path, callback.from_user.id, enabled)
        await callback.answer("Reminders turned on." if enabled else "Reminders turned off.")
        if callback.message:
            label = "Turn reminders off" if enabled else "Turn reminders on"
            status = "on" if enabled else "off"
            await callback.message.edit_text(
                f"Daily reminders are {status}. Reminder delivery will be available when scheduling is connected.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text=label, callback_data="toggle_reminders")]]
                ),
            )

    @router.message(Command("help"))
    @router.message(F.text == "Help")
    async def help_message(message: Message) -> None:
        await message.answer(
            "Use /today to see the shared reading, /plan to browse the full plan "
            "or /plan 17 to open the page containing Day 17, "
            "and /progress to see your private completion record. "
            "You can mark earlier readings complete from the plan."
        )

    return router
