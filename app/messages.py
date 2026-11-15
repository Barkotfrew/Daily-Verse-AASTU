"""Approved, fixed message templates for community reminders."""

DAILY_REMINDER = (
    "ሰላም የAASTU ECSF ቤተሰብ! 👋\n"
    "📖 Today's Bible Reading · Day {day}\n"
    "{ethiopian_date} · {gregorian_date}\n"
    "{reading}\n\n"
    "Take a little time today to read and reflect on God’s Word. "
    "We’re growing together, one day at a time. 💛\n"
    "— Daily Verse | AASTU ECSF"
)

REGISTRATION_REQUIRED = "Please send /start first so we can get you set up. 📖"

WELCOME_INTRO = (
    "Welcome to the AASTU ECSF Bible Reading App! 📖\n"
    "📌 What can this bot do?\n\n"
    "📖 View the daily reading and read Bible chapters.\n"
    "🗓 Follow the shared reading plan and mark readings as complete.\n"
    "📝 Reflect on a reading in the Mini App.\n"
    "🔔 Receive daily reading reminders at 06:00, 12:00, and 18:00 EAT.\n"
    "🏆 Choose to join the leaderboard in Settings.\n"
    "🔒 Your private journal entries are not shown on the leaderboard.\n\n"
    "After registering, choose an option below to open the day’s reading.\n\n"
    "Happy Reading!!📖"
)

HELP_COMMANDS = (
    "Use /today to see today's assigned reading.\n"
    "/plan to browse the full plan, or /plan 17 to open the page containing Day 17.\n"
    "Open a plan day to read its chapters and mark it complete.\n"
    "Use /progress to see your reading journey and streak.\n"
    "/leaderboard to view readers who opted in.\n"
    "/settings to manage your profile and leaderboard privacy.\n"
    "Open the Mini App for private journaling."
)

REGISTRATION_NAME_PROMPT = (
    "ስምዎን ያስገቡ።\n"
    "Please enter your name."
)

REGISTRATION_NAME_INVALID = "እባክዎ ስምዎን በትክክል ያስገቡ።\nPlease enter a valid name (2–64 characters)."

ACADEMIC_YEAR_OPTIONS = (
    "1st",
    "2nd",
    "3rd",
    "4th",
    "5th",
    "Out of batch",
    "Graduate",
    "Visitor",
)
REGISTRATION_YEAR_PROMPT = (
    "የትምህርት ዓመትዎን ከታች ካሉት አማራጮች ይምረጡ።\n"
    "Choose your year or status from the options below."
)
REGISTRATION_YEAR_INVALID = (
    "እባክዎ ከታች ካሉት አማራጮች አንዱን ይምረጡ።\n"
    "Please choose one of the options below."
)

REGISTRATION_DEPARTMENT_PROMPT = "የትምህርት ክፍልዎን ያስገቡ።\nPlease enter your department."
REGISTRATION_DEPARTMENT_INVALID = (
    "እባክዎ የክፍል ስምዎን በትክክል ያስገቡ።\n"
    "Please enter a valid department (2–80 characters)."
)

REGISTRATION_COMPLETE = (
    "Welcome to AASTU ECSF Bible Reading App, {name}! 📖\n\n"
    "We’re glad you’re here. Let’s grow in God’s Word together, one day at a time.\n\n"
    "Choose “Today’s Reading” below whenever you’re ready to begin."
)

REGISTRATION_EXISTING = (
    "Welcome back, {name}! 🙌\n\n"
    "We’re glad you’re here. Pick up where you left off, or open today’s reading below. "
    "Take it one day at a time."
)

DELETE_ACCOUNT_PROMPT = (
    "Delete your Daily Verse account? This also deletes your personal reading progress "
    "and reminder settings. You can register again later with /start."
)
DELETE_ACCOUNT_CANCELLED = "Deletion cancelled. Your account and progress are unchanged."
ACCOUNT_DELETED = "Your account and personal records have been deleted. Send /start to register again."

PROFILE_EDIT_PROMPT = {
    "name": "Send the name you want Daily Verse to use (2–64 characters).",
    "year": "Send your year of study (for example, 2 or 2nd year).",
    "department": "Send your department name (2–80 characters).",
}
PROFILE_EDIT_INVALID = {
    "name": "Please send a name using 2 to 64 characters.",
    "year": "Please send your year of study, such as 2 or 2nd year.",
    "department": "Please send a department name between 2 and 80 characters.",
}
PROFILE_EDIT_SAVED = "Your details have been updated."
