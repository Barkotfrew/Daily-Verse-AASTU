"""Approved, fixed message templates for community reminders."""

DAILY_REMINDER = (
    "ሰላም ተወዳጆች እንዴት ናችሁ? 👋👋👋\n"
    "የዛሬ ንባብ · ቀን {day}\n"
    "{ethiopian_date} · {gregorian_date}\n"
    "{reading}"
)

REGISTRATION_REQUIRED = "Please send /start first to create your account."

REGISTRATION_NAME_PROMPT = (
    "What is your name?\n"
    "It may appear on a future reading leaderboard."
)

REGISTRATION_NAME_INVALID = "Please enter your name using 2 to 64 characters."

REGISTRATION_YEAR_PROMPT = "What year of study are you in? For example: 2nd year."
REGISTRATION_YEAR_INVALID = "Please enter your year of study, such as 2 or 2nd year."

REGISTRATION_DEPARTMENT_PROMPT = "What is your department?"
REGISTRATION_DEPARTMENT_INVALID = "Please enter a department name between 2 and 80 characters."

REGISTRATION_COMPLETE = (
    "Thanks, your signup is complete. Welcome to Daily Verse. Choose an option below."
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
