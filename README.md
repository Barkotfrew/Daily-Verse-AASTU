# Daily Verse

Daily Verse is a Telegram Bible reading companion for the AASTU ECSF community. The supplied chronological schedule is stored in `data/reading_plan.json` as the canonical plan. It contains 231 days, from Tikimt 1 through Ginbot 21, mapped to October 11, 2026 through May 29, 2027.

## Requirements

- Python 3.11 or newer
- Windows PowerShell
- A Telegram bot token from BotFather (needed when Telegram handlers are added)

## Set up on Windows

From the project directory:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set `BOT_TOKEN` when you have created the bot. Keep `.env` private; it is ignored by Git. The initial foundation does not start Telegram polling yet.

## Initialize the local database

```powershell
python -m app.main
```

This creates `data/daily_verse.sqlite3` and the initial `users` table. Initialization is safe to repeat. The database is local development data and is ignored by Git.

## Run checks

```powershell
python -m unittest discover -s tests -v
```

## Current status

- Python configuration reads `BOT_TOKEN` and `DATABASE_PATH` from environment variables and `.env`.
- SQLite schema initialization is repeatable.
- The supplied 231-day reading plan loads from JSON and validates continuous day numbering and Gregorian dates.
- Bible text, Telegram handlers, and reminder scheduling are not included yet.

Next milestone: inspect and verify the candidate Amharic Bible dataset before connecting the reading interface. Confirm its book/chapter coverage and license; do not fabricate unavailable text.
