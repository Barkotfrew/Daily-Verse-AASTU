"""Approved, fixed message templates for community reminders."""

DAILY_REMINDER = (
    "ሰላም ተወዳጆች እንዴት ናችሁ? 👋👋👋\n"
    "የዛሬ ንባብ · ቀን {day}\n"
    "{ethiopian_date} · {gregorian_date}\n"
    "{reading}"
)

REGISTRATION_REQUIRED = "Please send /start first to register before using Daily Verse."

REGISTRATION_COMPLETE = (
    "ሰላም ተወዳጆች እንዴት ናችሁ? 👋👋👋\n"
    "You're registered. Welcome to Daily Verse. Choose an option below."
)

REGISTRATION_EXISTING = (
    "ሰላም ተወዳጆች እንዴት ናችሁ? 👋👋👋\n"
    "You're already registered. Choose an option below."
)

DELETE_ACCOUNT_PROMPT = (
    "Delete your Daily Verse account? This also deletes your personal reading progress "
    "and reminder settings. You can register again later with /start."
)
DELETE_ACCOUNT_CANCELLED = "Deletion cancelled. Your account and progress are unchanged."
ACCOUNT_DELETED = "Your account and personal records have been deleted. Send /start to register again."
