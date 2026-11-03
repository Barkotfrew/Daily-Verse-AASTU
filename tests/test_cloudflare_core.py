"""Offline tests for Cloudflare-facing pure helpers."""

import unittest

from app.cloudflare_core import (
    current_eat_date,
    escape_sql_text,
    format_today_message,
    private_message_parts,
    reminder_message,
    scheduled_eat_date,
    supported_command,
    verify_webhook_secret,
)


class CloudflareCoreTests(unittest.TestCase):
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

    def test_only_start_and_today_are_supported(self) -> None:
        self.assertEqual(supported_command("/start"), "start")
        self.assertEqual(supported_command("/start@ExampleBot payload"), "start")
        self.assertEqual(supported_command("/today"), "today")
        self.assertEqual(supported_command("Today's Reading"), "today")
        self.assertIsNone(supported_command("/plan"))

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

    def test_sql_text_escapes_single_quotes(self) -> None:
        self.assertEqual(escape_sql_text("God's word"), "'God''s word'")


if __name__ == "__main__":
    unittest.main()
