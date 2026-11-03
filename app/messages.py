"""Approved, fixed message templates for community reminders."""

DAILY_REMINDER = (
    "ሰላም ተወዳጆች እንዴት ናችሁ? 👋👋👋\n"
    "የዛሬ ንባብ · ቀን {day}\n"
    "{ethiopian_date} · {gregorian_date}\n"
    "{reading}"
)

REGISTRATION_REQUIRED = "Please send /start first to create your account."

REGISTRATION_NAME_PROMPT = (
    "What name or username should we show for you?\n"
    "A nickname is fine. It may appear on a future reading leaderboard."
)

REGISTRATION_NAME_INVALID = "Please send a name or nickname between 2 and 32 characters."

REGISTRATION_COMPLETE = (
    "Your name is saved. Welcome to Daily Verse. Choose an option below."
)

REGISTRATION_EXISTING = (
    "Welcome back, {name}. Choose an option below."
)

DELETE_ACCOUNT_PROMPT = (
    "Delete your Daily Verse account? This also deletes your personal reading progress "
    "and reminder settings. You can register again later with /start."
)
DELETE_ACCOUNT_CANCELLED = "Deletion cancelled. Your account and progress are unchanged."
ACCOUNT_DELETED = "Your account and personal records have been deleted. Send /start to register again."
