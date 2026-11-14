"""Offline tests for Cloudflare-facing pure helpers."""

import unittest

from app.cloudflare_core import (
    current_eat_date,
    normalize_display_name,
    normalize_signup_value,
    escape_sql_text,
    format_progress_message,
    books_visited_count,
    completed_this_eat_week,
    journey_progress_message,
    journey_timeline_keyboard,
    journey_timeline_page,
    format_leaderboard_message,
    mini_app_chapter_asset_url,
    mini_app_reader_keyboard,
    mini_app_reader_url,
    format_plan_page,
    format_today_message,
    is_start_command,
    plan_day_keyboard,
    private_message_parts,
    plan_page_for_command,
    plan_page_keyboard,
    registration_required,
    reminder_message,
    reminders_keyboard,
    reminders_settings_message,
    leaderboard_settings_message,
    settings_keyboard,
    today_keyboard,
    scheduled_eat_date,
    supported_command,
    verify_webhook_secret,
)


class CloudflareCoreTests(unittest.TestCase):
    def test_signup_name_is_trimmed_and_validated(self) -> None:
        self.assertEqual(normalize_display_name("  ባርኮ   ፍሬው "), "ባርኮ ፍሬው")
        self.assertEqual(normalize_display_name("Barki"), "Barki")
        self.assertIsNone(normalize_display_name("/today"))
        self.assertIsNone(normalize_display_name(" "))
        self.assertIsNone(normalize_display_name("x"))
        self.assertIsNone(normalize_display_name("A" * 65))
        self.assertEqual(
            normalize_signup_value(" Electrical and Computer Engineering ", 2, 80),
            "Electrical and Computer Engineering",
        )

    def test_webhook_secret_requires_both_values_and_matches_exactly(self) -> None:
        self.assertTrue(verify_webhook_secret("secret", "secret"))
        self.assertFalse(verify_webhook_secret("secret", "Secret"))
        self.assertFalse(verify_webhook_secret("", "secret"))
        self.assertFalse(verify_webhook_secret("secret", None))

    def test_scheduled_timestamp_maps_to_east_africa_date(self) -> None:
        # 04:00 UTC is 07:00 in Addis Ababa.
        self.assertEqual(scheduled_eat_date(1793678400000), "2026-11-03")

    def test_current_date_uses_eat_near_midnight_utc(self) -> None:
        from datetime import datetime, timezone

        instant = datetime(2026, 11, 2, 22, 30, tzinfo=timezone.utc)
        self.assertEqual(current_eat_date(instant).isoformat(), "2026-11-03")

    def test_supported_worker_commands(self) -> None:
        self.assertEqual(supported_command("/start"), "start")
        self.assertEqual(supported_command("/start@ExampleBot payload"), "start")
        self.assertEqual(supported_command("/today"), "today")
        self.assertEqual(supported_command("Today's Reading"), "today")
        self.assertEqual(supported_command("/progress"), "progress")
        self.assertEqual(supported_command("My Progress"), "progress")
        self.assertEqual(supported_command("/leaderboard"), "leaderboard")
        self.assertEqual(supported_command("Leaderboard"), "leaderboard")
        self.assertEqual(supported_command("/plan 17"), "plan")
        self.assertEqual(supported_command("Reading Plan"), "plan")
        self.assertEqual(supported_command("/settings"), "settings")
        self.assertEqual(supported_command("Settings"), "settings")
        self.assertTrue(is_start_command("/start@ExampleBot register"))
        self.assertFalse(is_start_command("/today"))
        self.assertFalse(is_start_command(None))

    def test_plan_commands_select_the_page_containing_a_day(self) -> None:
        self.assertEqual(plan_page_for_command("Reading Plan", 231), (1, None))
        self.assertEqual(plan_page_for_command("/plan 17", 231), (2, None))
        self.assertEqual(plan_page_for_command("/plan@DailyBot 231", 231), (17, None))
        self.assertEqual(plan_page_for_command("/plan 232", 231)[0], None)
        self.assertEqual(plan_page_for_command("/plan nope", 231)[0], None)

    def test_plan_page_format_preserves_exact_rows_and_day_order(self) -> None:
        rows = (
            {"plan_day": 1, "ethiopian_date": "ጥቅምት 1", "reading": "ዘፍጥረት 1-3",
             "gregorian_date": "2026-10-11"},
            {"plan_day": 2, "ethiopian_date": "ጥቅምት 2", "reading": "ዘፍጥረት 4-7",
             "gregorian_date": "2026-10-12"},
        )
        self.assertEqual(
            format_plan_page(rows, 1, 2),
            "Reading Plan · page 1/1 · 2 days\n\n"
            "Day 1 · ጥቅምት 1 · 2026-10-11\nዘፍጥረት 1-3\n\n"
            "Day 2 · ጥቅምት 2 · 2026-10-12\nዘፍጥረት 4-7",
        )

    def test_plan_keyboards_have_bounded_navigation_and_no_empty_rows(self) -> None:
        first_page = plan_page_keyboard(1, 15)
        self.assertEqual(first_page["inline_keyboard"][-1][0]["callback_data"], "planpage:2")
        self.assertTrue(all(first_page["inline_keyboard"]))

        last_page = plan_page_keyboard(2, 15)
        self.assertEqual(len(last_page["inline_keyboard"]), 2)
        self.assertEqual(last_page["inline_keyboard"][-1][0]["callback_data"], "planpage:1")

        first_day = plan_day_keyboard(1, 231)
        self.assertEqual(len(first_day["inline_keyboard"]), 2)
        self.assertEqual(first_day["inline_keyboard"][0][0]["callback_data"], "plan:2")
        final_day = plan_day_keyboard(231, 231)
        self.assertEqual(len(final_day["inline_keyboard"]), 2)
        self.assertEqual(final_day["inline_keyboard"][-1][0]["callback_data"], "planpage:17")

    def test_mini_app_reader_links_are_https_and_use_known_references(self) -> None:
        base = "https://daily-verse-aastu.pages.dev/"
        self.assertEqual(
            mini_app_reader_url(base, day=17),
            "https://daily-verse-aastu.pages.dev/?day=17",
        )
        self.assertEqual(
            mini_app_reader_url(base, book_id="GEN", chapter=1),
            "https://daily-verse-aastu.pages.dev/?book=GEN&chapter=1",
        )
        self.assertIsNone(mini_app_reader_url("http://example.com", day=1))
        self.assertIsNone(mini_app_reader_url(base, book_id="UNKNOWN", chapter=1))
        self.assertIsNone(mini_app_reader_url(base, book_id="GEN", chapter=151))
        self.assertEqual(
            mini_app_chapter_asset_url(base, "GEN", 1),
            "https://daily-verse-aastu.pages.dev/assets/chapters/GEN/1.json",
        )
        self.assertIsNone(mini_app_chapter_asset_url(base, "GEN", 0))
        self.assertEqual(
            mini_app_reader_keyboard(base, 17)["inline_keyboard"][0][0]["web_app"]["url"],
            "https://daily-verse-aastu.pages.dev/?day=17",
        )

    def test_start_is_registration_and_other_commands_require_it_first(self) -> None:
        self.assertFalse(registration_required("start", False))
        self.assertFalse(registration_required("today", True))
        self.assertTrue(registration_required("today", False))

    def test_today_message_uses_exact_entry_or_reports_no_entry(self) -> None:
        from datetime import date

        entry = {
            "plan_day": 24,
            "ethiopian_date": "ጥቅምት 24",
            "reading": "ዘፍጥረት 35-37",
            "gregorian_date": "2026-11-03",
        }
        self.assertEqual(
            format_today_message(entry, date(2026, 11, 3)),
            "Today's Reading\nDay 24 · ጥቅምት 24 · 2026-11-03\nዘፍጥረት 35-37",
        )
        self.assertEqual(
            format_today_message(None, date(2026, 11, 4)),
            "There is no scheduled reading for 2026-11-04 in this plan.",
        )

    def test_progress_message_is_private_summary_with_distinct_reading_days(self) -> None:
        self.assertEqual(
            format_progress_message(3, 231, (17, 8, 2)),
            "My Progress\n3 of 231 readings completed (1.3%).\n"
            "Recent completed days: 17, 8, 2",
        )
        self.assertEqual(
            format_progress_message(0, 0, ()),
            "My Progress\n0 of 0 readings completed (0.0%).\n"
            "Recent completed days: None yet",
        )
        streak = format_progress_message(
            3, 231, (3, 2, 1), streak="◆  READING STREAK\n3 days in a row\nBest · 3 days"
        )
        self.assertIn("My Progress\n◆  READING STREAK", streak)
        self.assertIn("Best · 3 days\n\n3 of 231", streak)

    def test_journey_week_count_uses_eat_calendar_week(self) -> None:
        from datetime import datetime, timezone

        records = (
            (1, "2026-11-08 21:30:00"),  # Monday 00:30 EAT
            (2, "2026-11-08 20:30:00"),  # Sunday 23:30 EAT
            (3, "not-a-time"),
        )
        now = datetime(2026, 11, 9, 1, tzinfo=timezone.utc)
        self.assertEqual(completed_this_eat_week(records, now), 1)

    def test_journey_summary_is_plan_focused_and_separates_current_status(self) -> None:
        entry = {
            "plan_day": 12, "ethiopian_date": "ጥቅምት 22",
            "reading": "Genesis 1-3", "gregorian_date": "2026-11-09",
        }
        text = journey_progress_message(3, 231, 2, 1, entry, False, "◆ 3 day streak")
        self.assertIn("DAILY VERSE · PERSONAL RECORD", text)
        self.assertIn("3 of 231 shared-plan readings completed", text)
        self.assertIn("This reading is still open for you.", text)
        self.assertIn("Completed readings · 3", text)
        self.assertIn("Bible books visited · 1", text)
        self.assertIn("Progress follows the shared reading plan.", text)

    def test_book_count_uses_only_completed_plan_assignments(self) -> None:
        entries = (
            {"plan_day": 1, "reading": "Genesis 1-3"},
            {"plan_day": 2, "reading": "Exodus 1"},
        )
        self.assertEqual(books_visited_count(entries, (1,)), 1)
        self.assertEqual(books_visited_count(entries, (1, 2)), 2)

    def test_timeline_uses_canonical_order_and_six_entry_pages(self) -> None:
        entries = tuple(
            {"plan_day": day, "ethiopian_date": f"date {day}",
             "reading": f"Genesis {day}", "gregorian_date": f"2026-11-{day:02d}"}
            for day in (7, 2, 6, 1, 5, 4, 3)
        )
        selected, page_count, text = journey_timeline_page(entries, {2}, 4, 1)
        self.assertEqual([row["plan_day"] for row in selected], [1, 2, 3, 4, 5, 6])
        self.assertEqual(page_count, 2)
        self.assertLess(text.index("Day 1"), text.index("Day 6"))
        keyboard = journey_timeline_keyboard(selected, 1, page_count)
        self.assertEqual(keyboard["inline_keyboard"][-2][0]["callback_data"], "journey:timeline:2")
        self.assertEqual(keyboard["inline_keyboard"][1][0]["callback_data"], "journey:entry:2")
        final, _, final_text = journey_timeline_page(entries, {2}, 4, 2)
        self.assertEqual([row["plan_day"] for row in final], [7])
        self.assertIn("Days 7–7", final_text)
        self.assertIsNone(journey_timeline_page(entries, set(), 4, 3)[0])

    def test_leaderboard_message_shows_only_the_consented_fields(self) -> None:
        self.assertEqual(
            format_leaderboard_message(({
                "display_name": "Barki",
                "academic_year": "4th",
                "completed": 12,
            },)),
            "Reading leaderboard\nOpted-in readers · completed readings\n\n"
            "01  Barki  ·  Year 4th  ·  12 readings",
        )
        self.assertIn("No readers have joined", format_leaderboard_message(()))

    def test_leaderboard_settings_requires_explicit_opt_in_and_can_be_reversed(self) -> None:
        self.assertIn("You are not listed", leaderboard_settings_message(False))
        self.assertIn("study year", leaderboard_settings_message(True))
        self.assertEqual(
            settings_keyboard(True, False)["inline_keyboard"][0][0],
            {"text": "Join leaderboard", "callback_data": "leaderboard:toggle"},
        )
        self.assertEqual(
            settings_keyboard(True, True)["inline_keyboard"][0][0]["text"],
            "Leave leaderboard",
        )

    def test_only_private_text_messages_are_extracted(self) -> None:
        update = {
            "message": {
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 456},
                "text": "/start",
            }
        }
        self.assertEqual(private_message_parts(update), (456, 123, "/start"))
        update["message"]["chat"]["type"] = "group"
        self.assertIsNone(private_message_parts(update))
        self.assertIsNone(private_message_parts({"inline_query": {"id": "x"}}))

    def test_reminder_uses_only_the_approved_fixed_template(self) -> None:
        self.assertEqual(
            reminder_message(24, "ጥቅምት 24", "2026-11-03", "ዘፍጥረት 35-37"),
            "ሰላም ተወዳጆች እንዴት ናችሁ? 👋👋👋\n"
            "የዛሬ ንባብ · ቀን 24\n"
            "ጥቅምት 24 · 2026-11-03\n"
            "ዘፍጥረት 35-37",
        )

    def test_personal_action_keyboards_and_reminder_setting_copy(self) -> None:
        keyboard = today_keyboard("https://daily-verse-aastu.pages.dev", 24)
        self.assertEqual(
            keyboard["inline_keyboard"][0][0]["web_app"]["url"],
            "https://daily-verse-aastu.pages.dev/?day=24",
        )
        self.assertEqual(
            keyboard["inline_keyboard"][2][0]["callback_data"], "complete:24"
        )
        self.assertEqual(
            reminders_keyboard(False)["inline_keyboard"][0][0]["callback_data"],
            "reminders:info",
        )
        self.assertIn("everyone who has started", reminders_settings_message(False))

    def test_settings_toggle_and_completion_callbacks_are_user_scoped_ids(self) -> None:
        from app.cloudflare_core import completion_button

        self.assertEqual(completion_button(231)[0]["callback_data"], "complete:231")
        self.assertEqual(
            completion_button(231, callback_prefix="plancomplete")[0]["callback_data"],
            "plancomplete:231",
        )
        self.assertNotIn(
            "reminders:toggle",
            [
                button.get("callback_data")
                for row in settings_keyboard(False, False)["inline_keyboard"]
                for button in row
            ],
        )

    def test_sql_text_escapes_single_quotes(self) -> None:
        self.assertEqual(escape_sql_text("God's word"), "'God''s word'")


if __name__ == "__main__":
    unittest.main()
