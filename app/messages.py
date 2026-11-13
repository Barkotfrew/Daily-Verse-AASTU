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
    "ሰላም ተወዳጆች እንዴት ናችሁ? 👋👋👋\n\n"
    "እንኳን ወደ AASTU ECSF የመጽሐፍ ቅዱስ ንባብ መተግበሪያ በደህና መጡ! 📖\n"
    "📌 ይህን ቦት በመጠቀም፦\n\n"
    "1️⃣ የዕለቱን ንባብ እና የመጽሐፍ ቅዱስ ምዕራፎችን ማንበብ ይችላሉ።\n"
    "2️⃣ የጋራውን የንባብ እቅድ ተከታትለው ንባብዎን ሲጨርሱ ምልክት ማድረግ ይችላሉ።\n"
    "3️⃣ ከንባብ ቀን ጋር የተያያዘ የግል ማስታወሻ ወይም ጸሎት በMini App ውስጥ መጻፍ ይችላሉ።\n\n"
    "🔔 የዕለታዊ ማስታወሻዎችን ከSettings ማብራት ወይም ማጥፋት ይችላሉ።\n"
    "🏆 በመሪ ሰሌዳው ላይ መታየት ከፈለጉ ከSettings በፈቃድዎ ይቀላቀሉ።\n\n"
    "🔒 የግል ማስታወሻዎችዎ በመሪ ሰሌዳ ላይ አይታዩም።\n\n"
    "ከተመዘገቡ በኋላ የዕለቱን ንባብ ከታች ካሉት አማራጮች ይክፈቱ።\n\n"
    "Welcome to the AASTU ECSF Bible Reading App! 📖\n"
    "📌 What can this bot do?\n\n"
    "1️⃣ Read the daily assignment and Bible chapters.\n"
    "2️⃣ Follow the shared reading plan and mark readings as complete.\n"
    "3️⃣ Write a private note or prayer for a reading day in the Mini App.\n\n"
    "🔔 Turn daily reminders on or off in Settings.\n"
    "🏆 Opt in to appear on the leaderboard from Settings.\n\n"
    "🔒 Your private journal entries are not shown on the leaderboard.\n\n"
    "After registering, choose an option below to open the day’s reading."
)

REGISTRATION_NAME_PROMPT = (
    "ለመመዝገብ ምን ስም እንጠቀም?\n"
    "ስምዎና የትምህርት ዓመትዎ በመሪ ሰሌዳው ላይ የሚታዩት ከSettings ውስጥ መሳተፍን ከመረጡ ብቻ ነው።"
)

REGISTRATION_NAME_INVALID = "እባክዎ ከ2 እስከ 64 ቁምፊዎች ያሉትን ስም ያስገቡ።"

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
REGISTRATION_YEAR_INVALID = "እባክዎ ከታች ካሉት የትምህርት ዓመት ወይም ሁኔታ አማራጮች አንዱን ይምረጡ።"

REGISTRATION_DEPARTMENT_PROMPT = "የትምህርት ክፍልዎ (Department) ምንድን ነው?"
REGISTRATION_DEPARTMENT_INVALID = "እባክዎ ከ2 እስከ 80 ቁምፊዎች ያሉትን የክፍል ስም ያስገቡ።"

REGISTRATION_COMPLETE = (
    "Welcome to Daily Verse — AASTU ECSF, {name}! 📖\n\n"
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
