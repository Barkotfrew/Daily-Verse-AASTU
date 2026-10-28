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

This creates `data/daily_verse.sqlite3` and the user and reading-completion tables. Initialization is safe to repeat. The database is local development data and is ignored by Git.

## Start the Telegram bot

Set `BOT_TOKEN` in `.env`, then run:

```powershell
python -m app.main
```

The bot uses long polling and needs the process to stay running. `/start`, `/today`, `/plan`, `/progress`, `/settings`, and `/help` are wired. `/plan` pages through the full schedule; `/plan 17` opens the page containing Day 17, and individual days open for detail/actions. EAT is represented as a fixed UTC+3 offset, so Windows does not need a separate timezone database. Daily reminders are not scheduled yet, and chapter reading clearly reports that verified Bible text is not connected.

## Run checks

```powershell
python -m unittest discover -s tests -v
```

## Current status

- Python configuration reads `BOT_TOKEN` and `DATABASE_PATH` from environment variables and `.env`.
- SQLite schema initialization is repeatable.
- The supplied 231-day reading plan loads from JSON and validates continuous day numbering and Gregorian dates.
- A normalized Bible JSON access layer supports full chapters, individual verses, and merged verse-number ranges. Tests use explicitly synthetic fixture strings, never Bible quotations.
- Assigned readings expand into ordered canonical book/chapter requests, and chapter messages repeat references while splitting long text without dropping or reordering verse content.
- A shared reference parser maps English and Amharic names for all 66 Protestant books to canonical IDs and parses chapter and verse ranges.
- Bible text, Telegram handlers, and reminder scheduling are not included yet.

## Bible data source review

The candidate [Amharic Bible JSON repository](https://github.com/magna25/amharic-bible-json) lists 66 individual Protestant Bible books and provides a 5.44 MB combined JSON file. Its README says the data came from WordProject and GeezExperience, that it has not been checked for consistency, and that some Amharic verse numbers are combined into ranges with the text stored on the final verse number. The repository has an MIT license and its README says the data is free to use. WordProject's own terms only grant distribution for Bible content that is in the public domain; the provenance of the GeezExperience material and the rights for the translation need confirmation before bundling or redistributing this scrape. No English translation is included in this candidate.

The local copy is in `data/bible/source/amharic_bible.json`; the repository adapter reads its source format directly and maps the 66 books to the bot's canonical IDs. Empty verse slots before text are rendered as combined verse ranges. The adapter flags chapters with trailing empty verse slots and the chapter reader refuses to present those chapters as complete. A malformed chapter label is treated as unavailable rather than guessed. The dataset does not contain English text.

The locally inspected combined file has 66 books and 1,189 chapter rows, but one chapter label is malformed and 480 verse positions are empty. Against the supplied 231-day plan, 806 referenced chapters are complete, 22 have trailing empty verse slots, and none of the plan's chapter references are absent by number. These counts describe source structure, not a verse-by-verse accuracy audit. The README says the data is free to use and documents combined verse numbering; the repository's MIT license names the software author, while the Bible-text scrape is attributed to WordProject and GeezExperience. Confirm redistribution rights for the source content before a public release.

Next milestone: implement bilingual inline queries against this same Amharic repository and find a separately licensed English translation before returning English Bible text.
