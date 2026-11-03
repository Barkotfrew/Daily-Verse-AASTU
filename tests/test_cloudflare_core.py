"""Offline tests for Cloudflare-facing pure helpers."""

import unittest

from app.cloudflare_core import (
    escape_sql_text,
    private_message_parts,
    reminder_message,
    scheduled_eat_date,
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
