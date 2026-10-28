# Daily Verse

Daily Verse is a Telegram Bible reading companion for the AASTU ECSF community. The supplied chronological schedule is stored in `data/reading_plan.json` as the canonical plan. It contains 231 days, from Tikimt 1 through Ginbot 21, mapped to October 11, 2026 through May 29, 2027.

## Requirements

- Python 3.11 or newer
- Windows PowerShell
- A Telegram bot token from BotFather

## Set up on Windows

From the project directory:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set `BOT_TOKEN`. Keep `.env` private; it is ignored by Git.

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

The bot uses long polling and needs the process to stay running. `/start`, `/today`, `/plan`, `/progress`, `/settings`, and `/help` are wired. `/plan` pages through the full schedule; `/plan 17` opens the page containing Day 17, and individual days open for detail/actions. Chapter reading uses the local Amharic source data and reports unavailable or incomplete chapters. Daily reminders are not scheduled yet.

## Run checks

```powershell
python -m unittest discover -s tests -v
```

## Current status

- Python configuration reads `BOT_TOKEN`, `DATABASE_PATH`, and optional `MINI_APP_URL` from environment variables and `.env`.
- SQLite schema initialization is repeatable.
- The supplied 231-day reading plan loads from JSON and validates continuous day numbering and Gregorian dates.
- The Amharic Bible source adapter supports full chapters, individual verses, and merged verse-number ranges. Tests use explicitly synthetic fixture strings, never Bible quotations.
- Assigned readings expand into ordered canonical book/chapter requests, and chapter messages repeat references while splitting long text without dropping or reordering verse content.
- A shared reference parser maps English and Amharic names for all 66 Protestant books to canonical IDs and parses chapter and verse ranges.
- Telegram chapter reading and bilingual inline reference search use the same Bible data access layer.
- A static Telegram Mini App reader is built for GitHub Pages and loads only the selected chapter asset.
- Daily reminders are not implemented yet.

## Bible data source review

The candidate [Amharic Bible JSON repository](https://github.com/magna25/amharic-bible-json) lists 66 individual Protestant Bible books and provides a 5.44 MB combined JSON file. Its README says the data came from WordProject and GeezExperience, that it has not been checked for consistency, and that some Amharic verse numbers are combined into ranges with the text stored on the final verse number. The repository has an MIT license and its README says the data is free to use. WordProject's own terms only grant distribution for Bible content that is in the public domain; the provenance of the GeezExperience material and the rights for the translation need confirmation before bundling or redistributing this scrape. No English translation is included in this candidate.

The local copy is in `data/bible/source/amharic_bible.json`; the repository adapter reads its source format directly and maps the 66 books to the bot's canonical IDs. Empty verse slots before text are rendered as combined verse ranges. The adapter flags chapters with trailing empty verse slots and the chapter reader refuses to present those chapters as complete. A malformed chapter label is treated as unavailable rather than guessed. The dataset does not contain English text.

The locally inspected combined file has 66 books and 1,189 chapter rows, six malformed chapter labels, and 480 empty verse positions. Against the supplied 231-day plan, 806 referenced chapters are complete, 22 have trailing empty verse slots, and none of the plan's chapter references are absent by number. The static site builder preserves malformed labels as unavailable and does not publish those chapter files. These counts describe source structure, not a verse-by-verse accuracy audit. The README says the data is free to use and documents combined verse numbering; the repository's MIT license names the software author, while the Bible-text scrape is attributed to WordProject and GeezExperience. Confirm redistribution rights for the source content before a public release.

## Inline Bible search

Inline reference search accepts English and Amharic book names, for example `Genesis 1:1`, `Psalm 23:1`, `ዘፍጥረት 1`, and `መዝሙረ ዳዊት 23:1`. The current dataset provides Amharic text only, so results are labeled Amharic even when the query uses an English book name. Chapter searches return selectable verse results. The result button opens the requested complete chapter in a private chat when that chapter is complete in the source data.

Inline mode is enabled in BotFather with `/setinline`. Test in Telegram by typing `@AASTU_ECSF_DailyVerse_2026Bot Genesis 1:1` or `@AASTU_ECSF_DailyVerse_2026Bot ዘፍጥረት 1`. Inline mode requires the bot to be running and the data file to be installed.

## GitHub Pages Mini App

The project repository is public, so GitHub Pages is available on GitHub Free. The published Mini App URL for this repository is `https://barkotfrew.github.io/Daily-Verse-AASTU/` once Pages is enabled. In GitHub, open **Settings → Pages** and choose **GitHub Actions** as the build and deployment source. The workflow `.github/workflows/deploy-miniapp.yml` builds and publishes the static reader from `main`.

The builder splits Bible text into chapter-sized assets under the generated `webapp/dist` directory, so opening one chapter does not download the full dataset. To preview locally:

```powershell
python scripts/build_miniapp.py
python -m http.server 8000 --directory webapp/dist
```

Open `http://localhost:8000/?book=GEN&chapter=1` in a browser. After Pages succeeds, set `MINI_APP_URL=https://barkotfrew.github.io/Daily-Verse-AASTU` in the bot host's environment and restart the bot. Until then, inline chapter searches keep their private-chat fallback. The Bible text and Mini App are public; verify text redistribution rights before enabling public deployment.

Next milestone: enable GitHub Pages and test the chapter button in Telegram, then implement daily reminders. English Bible text still requires a separately licensed source.
