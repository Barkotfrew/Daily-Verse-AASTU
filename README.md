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
pip install -r requirements-bot.txt
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

The bot uses long polling and needs the process to stay running. A user's first `/start` creates a pending account and asks for their name, year of study, and department in sequence. The menu and bot features unlock after all three are saved. Settings lets each user manage reminders, opt into or out of the shared leaderboard, edit their own name/year/department, and request account deletion; deletion requires confirmation and removes only that user's profile, progress, journal, and reminder records. `/start`, `/today`, `/plan`, `/progress`, `/journal`, `/leaderboard`, `/settings`, and `/help` are wired. The main menu places Leaderboard alongside My Progress and My Journal. `/leaderboard` shows the same top ten opt-in readers to each user, identified by chosen name, study year, and completed-reading count. `/plan` pages through the full schedule; `/plan 17` opens the page containing Day 17, and individual days open for detail/actions. Chapter reading uses the local Amharic source data and reports unavailable or incomplete chapters. The reminder service is available but is disabled by default until the deployment clock and persistent SQLite storage have been checked.

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
- Assigned chapter read toggles are saved per Telegram user and plan day using Telegram Mini App CloudStorage, with browser local storage as a fallback. Chapter read toggles are reader state; users still mark a plan day complete explicitly in the bot to update `/progress`.
- `/progress` shows assigned-plan completion totals, a consecutive-plan-day streak with a best streak, and the five most recent plan readings marked complete. This is plan history, not a claim of whole-Bible coverage. A missed scheduled day ends the current streak but does not affect completed readings or the shared schedule; the current day's reading can still be completed later that day.
- `/journal` and the My Journal menu show a private reflection journal. Each entry is linked to a plan day and can include an optional verse reference and prayer note. Entries are scoped to the owner's Telegram account, never shown on the leaderboard, and removed when that account is deleted.
- `/leaderboard` and the main-menu button show the same top ten opted-in readers to every user who opens it in private chat. Each row contains the chosen display name, study year, and completed-reading count. Joining is optional in Settings; readers can leave at any time, which removes them from the list.
- Streak and leaderboard support is available in both the active local aiogram/SQLite bot and the Cloudflare Worker migration.
- Daily reminders use a fixed Amharic template, the shared plan date, and individual private-chat opt-in state. Each reminder has an “Open today's reading” action, plus separate mark-complete and plan actions. The scheduler checks at 7:00 AM EAT and records one delivery per user/date to avoid resending completed deliveries after restarts.
- Reminder sends are batched at up to 20 per second, retried up to five attempts with backoff, and isolated so a failed recipient does not interrupt other deliveries. Telegram-forbidden private chats are opted out automatically.
- Set `REMINDER_SCHEDULER_ENABLED=true` only after verifying that the deployment runs continuously at the configured time and its SQLite file survives process restarts/redeploys. `REMINDER_TIME` uses 24-hour EAT (`07:00` by default); it defaults to a disabled scheduler, and `/settings` reports whether delivery is paused or active. Reminders continue after a reading is marked complete, and users can turn them off individually.

## Bible data source review

The candidate [Amharic Bible JSON repository](https://github.com/magna25/amharic-bible-json) lists 66 individual Protestant Bible books and provides a 5.44 MB combined JSON file. Its README says the data came from WordProject and GeezExperience, that it has not been checked for consistency, and that some Amharic verse numbers are combined into ranges with the text stored on the final verse number. The repository has an MIT license and its README says the data is free to use. WordProject's own terms only grant distribution for Bible content that is in the public domain; the provenance of the GeezExperience material and the rights for the translation need confirmation before bundling or redistributing this scrape. No English translation is included in this candidate.

The local copy is in `data/bible/source/amharic_bible.json`; the repository adapter reads its source format directly and maps the 66 books to the bot's canonical IDs. Empty verse slots before text are rendered as combined verse ranges. The adapter flags chapters with trailing empty verse slots and the chapter reader refuses to present those chapters as complete. A malformed chapter label is treated as unavailable rather than guessed. The dataset does not contain English text.

The locally inspected combined file has 66 books and 1,189 chapter rows, six malformed chapter labels, and 480 empty verse positions. After applying the reviewed correction sidecar, 825 of the plan's 826 unique chapter references are complete. The remaining scheduled gap is 2 Kings 11: the available source has verses 1–20, followed by a blank verse 21 slot. Twenty-two other incomplete chapters are outside the current plan. The static site builder preserves malformed labels as unavailable and does not publish those chapter files. These counts describe source structure, not a verse-by-verse accuracy audit. The README says the data is free to use and documents combined verse numbering; the repository's MIT license names the software author, while the Bible-text scrape is attributed to WordProject and GeezExperience. Confirm redistribution rights for the source content before a public release.

Small reviewed fixes to the combined source are stored in adjacent `*.corrections.json` sidecars. `amharic_bible.corrections.json` contains owner-provided text and chapter-end corrections for the supplied passages; it does not rewrite the upstream minified source dump. The scheduled 2 Kings 11 gap remains unavailable until its missing source text is supplied and reviewed.

## Inline Bible search

Inline reference search accepts English and Amharic book names, for example `Genesis 1:1`, `Psalm 23:1`, `ዘፍጥረት 1`, and `መዝሙረ ዳዊት 23:1`. The current dataset provides Amharic text only, so results are labeled Amharic even when the query uses an English book name. Chapter searches return selectable verse results. The result button opens the requested complete chapter in a private chat when that chapter is complete in the source data.

Inline mode is enabled in BotFather with `/setinline`. Test in Telegram by typing `@AASTU_ECSF_DailyVerse_2026Bot Genesis 1:1` or `@AASTU_ECSF_DailyVerse_2026Bot ዘፍጥረት 1`. Inline mode requires the bot to be running and the data file to be installed.

## Cloudflare Pages Mini App

The Mini App is hosted separately from the personal GitHub Pages site. The Cloudflare Pages project uses the GitHub repository with build command `python scripts/build_miniapp.py` and output directory `webapp/dist`. Cloudflare's Git integration rebuilds the static reader when changes are pushed.

The builder creates chapter-sized assets and a copy of the shared reading plan under the generated `webapp/dist` directory. The `Read Chapters` button in a private chat opens the Mini App directly on that day's assigned chapters. For inline chapter searches, its button opens the requested chapter. The app fetches only the chapters it needs. Read checkmarks are stored in Telegram CloudStorage under one small key per reading-plan day (within Telegram's 1,024-key per-user limit); outside Telegram, browser local storage is used. These checkmarks do not mark the day complete in the bot's private progress record.

To preview locally:

```powershell
python scripts/build_miniapp.py
python -m http.server 8000 --directory webapp/dist
```

Open `http://localhost:8000/?book=GEN&chapter=1` in a browser. After Cloudflare deploys, set `MINI_APP_URL=https://daily-verse-aastu.pages.dev` in the bot host's environment and restart the bot. The Bible text and Mini App are public; verify text redistribution rights before public release.

## Cloudflare Worker migration (in progress)

Cloudflare is the selected zero-cost hosting direction because the project already uses Pages. This is a separate backend migration: the running aiogram bot still uses long polling and local SQLite. The Worker remains an incomplete migration and is not the active bot backend. Do not point Telegram's production webhook at the Worker until the complete Worker flow has been tested in Cloudflare's runtime.

The Worker supports private signup, `/today`, `/progress`, `/leaderboard`, `/settings`, `/help`, paged `/plan` browsing, the assigned-reading Mini App button, bilingual English/Amharic reference queries in inline mode, and personal completion. `Mark as Read` inserts one `(Telegram user, plan day)` completion, so repeated taps do not increase progress twice. `/progress` includes current and best consecutive-day streaks derived from those completion rows; a missed day ends the streak without changing completion history. `/settings` shows the user's profile, toggles reminder preference and explicit leaderboard opt-in, allows editing the user's name/year/department, and offers account deletion with a confirmation step. The main menu places Leaderboard beside My Progress. The same top ten opted-in readers are shown to each user, identified by chosen name, study year, and completed-reading count. Progress remains private. Bible text is fetched one chapter at a time from the same static Pages assets used by the Mini App; the Worker does not keep a second Bible copy in D1. Inline results use the verified Amharic source text and label it accordingly.

Worker reminders use an at-least-once Cloudflare Queue with a D1 delivery ledger and an atomic claim before sending. The Cron handler starts at 7:00 AM EAT and processes up to 100 registered, reminder-enabled users per minute in ascending Telegram ID order; for the expected 1,200 users this schedules the batch over about 12 minutes. Users' reminders continue after completion. The final reminder for a date is never inferred beyond the plan. A network failure after Telegram accepts a message but before its response reaches the Worker is inherently ambiguous because Telegram's send API has no idempotency key; the ledger prevents ordinary duplicate queue deliveries and restarts, while retries may repeat only in that ambiguous failure case.

Reminder scheduling is intentionally **not enabled in `wrangler.toml` yet**. First create a Cloudflare Queue named `daily-verse-reminders`, then add the following bindings and trigger to `wrangler.toml`; only do this after the Worker and Queue have been tested in Cloudflare's runtime:

```toml
[[queues.producers]]
queue = "daily-verse-reminders"
binding = "REMINDER_QUEUE"

[[queues.consumers]]
queue = "daily-verse-reminders"
max_batch_size = 20
max_batch_timeout = 5
max_retries = 5

[triggers]
crons = ["* 4 * * *"] # 04:00–04:59 UTC is 07:00–07:59 EAT
```

Apply migration `0005_reminder_runs.sql` along with the earlier D1 migrations before testing the scheduler. The first registration command and all reminders remain separate from the current polling bot until a deliberate backend switch; do not set Telegram's production webhook to the Worker as part of local testing.

For Worker inline search, set Telegram's webhook to include `inline_query` updates only after the Worker deployment is intentionally being tested. Registered users can query references such as `Genesis 1:1`, `Psalm 23:1`, `ዘፍጥረት 1`, and `መዝሙረ ዳዊት 23:1` in any supported chat. Chapter results offer a button to open the full chapter in the Mini App. The `/today` response and selected plan days open the assigned chapters there. These links depend on the matching chapter assets being deployed at `MINI_APP_URL`.

The D1 base schema is in `cloudflare/worker/migrations/0001_schema.sql`. Later migrations add profile fields (`0003_add_display_name.sql`, `0004_add_academic_profile.sql`), reminder runs (`0005_reminder_runs.sql`), leaderboard opt-in (`0006_add_leaderboard_opt_in.sql`), and profile-edit state (`0007_add_profile_edit_state.sql`). The canonical reading plan is exported to `cloudflare/worker/seed/0002_reading_plan.sql`; regenerate it after an approved plan change with:

```powershell
python scripts/export_d1_reading_plan.py
```

Cloudflare's Python Worker toolchain uses `uv` and `pywrangler`. Install uv and sync its isolated tool dependencies:

```powershell
winget install --id=astral-sh.uv -e
$env:UV_PROJECT_ENVIRONMENT = ".venv-pywrangler"
uv sync --dev
```

The Pywrangler CLI environment uses `.venv-pywrangler` so it does not replace the aiogram packages used by the local bot environment. Pywrangler manages a separate `.venv-workers` environment for the Python version selected by the Worker's compatibility date. The bot's pip dependency list is kept separately in `requirements-bot.txt` because Pywrangler expects Worker dependencies to come from `pyproject.toml` and stops when a root `requirements.txt` is present.

For a local Worker preview, create `.dev.vars` from `.dev.vars.example`, set local credentials there, create a D1 database in Cloudflare, and replace the placeholder ID in `wrangler.toml`. Apply the schema and plan seed to local D1, then start the Worker:

```powershell
npx wrangler d1 migrations apply daily-verse-aastu --local
npx wrangler d1 execute daily-verse-aastu --local --file=cloudflare/worker/seed/0002_reading_plan.sql
uv run pywrangler dev
```

The production polling bot remains separate; do not register a Telegram webhook yet. Before a future test deployment, migrate the schema, import the plan, set credentials as Worker secrets, and verify every bot flow. Do not enable the Queue binding or Cron trigger until the Worker and scheduler have been tested in the deployed runtime. The Worker runtime uses Python through Pyodide; verify package compatibility before choosing Python dependencies.

English Bible text still requires a separately licensed source.
