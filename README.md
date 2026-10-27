# Daily Verse

Daily Verse is a Telegram Bible reading companion for the AASTU ECSF community. The repository currently contains the first project foundation; the authoritative reading plan and Bible texts have not yet been supplied or verified.

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
- No reading plan, Bible text, Telegram handlers, or reminder scheduler is included yet.

Next milestone: add the real shared reading plan loader and validation after importing the owner's authoritative schedule. Keep missing schedule entries explicit; do not invent them.
