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
- Daily reminders use a fixed Amharic template, the shared plan date, and individual private-chat opt-in state. Each reminder has an “Open today's reading” action, plus separate mark-complete and plan actions. The scheduler checks at 06:00, 12:00, and 18:00 EAT and records one delivery per user/date/time to avoid resending completed deliveries after restarts.
- Reminder sends are batched at up to 20 per second, retried up to five attempts with backoff, and isolated so a failed recipient does not interrupt other deliveries. Telegram-forbidden private chats are opted out automatically.
- Set `REMINDER_SCHEDULER_ENABLED=true` only after verifying that the deployment runs continuously at the configured times and its SQLite file survives process restarts/redeploys. `REMINDER_TIMES` is a comma-separated list of 24-hour EAT times (`06:00,12:00,18:00` by default); the scheduler remains disabled by default, and `/settings` reports whether delivery is paused or active. Reminders continue after a reading is marked complete, and users can turn them off individually.

## Bible data source review

The candidate [Amharic Bible JSON repository](https://github.com/magna25/amharic-bible-json) lists 66 individual Protestant Bible books and provides a 5.44 MB combined JSON file. Its README says the data came from WordProject and GeezExperience, that it has not been checked for consistency, and that some Amharic verse numbers are combined into ranges with the text stored on the final verse number. The repository has an MIT license and its README says the data is free to use. WordProject's own terms only grant distribution for Bible content that is in the public domain; the provenance of the GeezExperience material and the rights for the translation need confirmation before bundling or redistributing this scrape. No English translation is included in this candidate.

The local copy is in `data/bible/source/amharic_bible.json`; the repository adapter reads its source format directly and maps the 66 books to the bot's canonical IDs. Empty verse slots before text are rendered as combined verse ranges. The adapter flags chapters with trailing empty verse slots and the chapter reader refuses to present those chapters as complete. A malformed chapter label is treated as unavailable rather than guessed. The dataset does not contain English text.

The locally inspected combined file has 66 books and 1,189 chapter rows, six malformed chapter labels, and 480 empty verse positions. After applying the reviewed correction sidecar, all 826 of the plan's unique chapter references are complete. The source had 2 Kings 11 verses 1–20 followed by a blank verse 21 slot; the missing verse text was present as the first entry under the following source chapter and is now assigned to 2 Kings 11:21 in the correction sidecar. Twenty-two other incomplete chapters are outside the current plan. The static site builder preserves malformed labels as unavailable and does not publish those chapter files. These counts describe source structure, not a verse-by-verse accuracy audit. The README says the data is free to use and documents combined verse numbering; the repository's MIT license names the software author, while the Bible-text scrape is attributed to WordProject and GeezExperience. Confirm redistribution rights for the source content before a public release.

Small reviewed fixes to the combined source are stored in adjacent `*.corrections.json` sidecars. `amharic_bible.corrections.json` contains owner-provided text, chapter-end corrections, and the recovered 2 Kings 11:21; it does not rewrite the upstream minified source dump.

## Inline Bible search

Inline reference search accepts English and Amharic book names, for example `Genesis 1:1`, `Psalm 23:1`, `ዘፍጥረት 1`, and `መዝሙረ ዳዊት 23:1`. The current dataset provides Amharic text only, so results are labeled Amharic even when the query uses an English book name. Chapter searches return selectable verse results. The result button opens the requested complete chapter in a private chat when that chapter is complete in the source data.

Inline mode is enabled in BotFather with `/setinline`. Test in Telegram by typing `@AASTU_ECSF_DailyVerse_2026Bot Genesis 1:1` or `@AASTU_ECSF_DailyVerse_2026Bot ዘፍጥረት 1`. Inline mode requires the bot to be running and the data file to be installed.

## Cloudflare Pages Mini App

The Mini App is hosted separately from the personal GitHub Pages site. The Pages-specific Wrangler config is `webapp/wrangler.toml`; keep it separate from the root `wrangler.toml`, which configures the Telegram Worker and D1 binding. In the Cloudflare Pages Git project, set the root directory to `webapp`, the build command to `python ../scripts/build_miniapp.py`, and the output directory to `dist`. Set the Pages build environment variable `DAILY_VERSE_API_URL` to the HTTPS base URL of the deployed Worker (for example, `https://<your-worker-subdomain>.workers.dev`). The build writes that value to generated `config.js`; do not commit a deployed API URL if you use separate environments. The build script resolves the repository root from its own location and generates the static chapter assets into `webapp/dist`.

The builder creates chapter-sized assets and a copy of the shared reading plan under the generated `webapp/dist` directory. The `Read Chapters` button in a private chat opens the Mini App directly on that day's assigned chapters. For inline chapter searches, its button opens the requested chapter. The app fetches only the chapters it needs. Read checkmarks are stored in Telegram CloudStorage under one small key per reading-plan day (within Telegram's 1,024-key per-user limit); outside Telegram, browser local storage is used. These checkmarks do not mark the day complete in the bot's private progress record.

To preview locally:

```powershell
python scripts/build_miniapp.py
python -m http.server 8000 --directory webapp/dist
```

Open `http://localhost:8000/?book=GEN&chapter=1` in a browser. After Cloudflare deploys, set `MINI_APP_URL=https://daily-verse-aastu.pages.dev` in the bot host's environment and restart the bot. The Bible text and Mini App are public; verify text redistribution rights before public release.

## Cloudflare Worker and D1 backend

Cloudflare Pages hosts the Mini App, and the Telegram webhook is currently routed to the Cloudflare Worker. The aiogram bot and SQLite database remain useful for local development; changes to that local database do not automatically reach D1. D1 is the production Worker database.

The Worker supports private signup, `/today`, `/progress`, `/journal`, `/leaderboard`, `/settings`, `/help`, paged `/plan` browsing, the assigned-reading Mini App button, bilingual English/Amharic reference queries in inline mode, and personal completion. The Mini App journal API validates Telegram Web App `initData` and restricts every read, write, and delete to the registered Telegram account. Once the Pages build has `DAILY_VERSE_API_URL` configured, the first authenticated use copies old device-local journal entries to D1 idempotently and then loads entries from the account; bot and Mini App journals share the same private D1 table. If API configuration or authentication is unavailable, entries stay saved on-device. Reading marks and bookmarks saved by the Mini App remain device/Telegram CloudStorage data and are not part of the SQLite-to-D1 importer. `Mark as Read` inserts one `(Telegram user, plan day)` completion, so repeated taps do not increase progress twice. `/progress` includes current and best consecutive-day streaks derived from those completion rows; a missed day ends the streak without changing completion history. `/journal` stores private reflection entries in D1, offers day and optional verse/prayer fields, and scopes every view to its owner. `/settings` shows the user's profile, toggles reminder preference and explicit leaderboard opt-in, allows editing the user's name/year/department, and offers account deletion with a confirmation step. The same top ten opted-in readers are shown to each user, identified by chosen name, study year, and completed-reading count. Progress and journal entries are private. Bible text is fetched one chapter at a time from the same static Pages assets used by the Mini App; the Worker does not keep a second Bible copy in D1. Inline results use the verified Amharic source text and label it accordingly.

Worker reminders use an at-least-once Cloudflare Queue with a D1 delivery ledger and an atomic claim before sending. The Cron handler runs through the 06:00, 12:00, and 18:00 EAT hour windows, processing up to 100 registered, reminder-enabled users per minute in ascending Telegram ID order; for the expected 1,200 users each window queues the batch over about 12 minutes. Each time has its own run and delivery record. Reminders include an “Open today's reading” button and continue after completion. The final reminder for a date is never inferred beyond the plan. A network failure after Telegram accepts a message but before its response reaches the Worker is inherently ambiguous because Telegram's send API has no idempotency key; the ledger prevents ordinary duplicate queue deliveries and restarts, while retries may repeat only in that ambiguous failure case.

The root `wrangler.toml` configures the reminder Queue and Cron schedule. Create the Queue once, apply the D1 migrations, set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_WEBHOOK_SECRET` as Worker secrets, and deploy the Worker configuration to activate it. The Cron expression checks the three EAT hours; the Worker sends only at 06:00, 12:00, and 18:00 EAT. Queue delivery has at-least-once semantics, so the D1 delivery ledger protects against normal duplicate sends. Deployment activates recurring Telegram reminders for registered users with reminders enabled.

```powershell
npx wrangler queues create daily-verse-reminders
npx wrangler d1 migrations apply daily-verse-aastu --remote
npx wrangler deploy
```

The Worker sends the direct “Open today's reading” button and continues to respect each user's reminder preference. Review the D1 cohort and confirm the Queue exists before deploying; deployment activates recurring Telegram reminders.

### Import existing local profiles, progress, and journal entries

Local aiogram/SQLite records are not copied into D1 automatically. The exporter below reads the SQLite file in read-only mode and creates a **private, ignored SQL file**. It includes profiles and preferences, completed plan days, and journal entries. It does not include reminder-delivery history. The generated SQL is merge-only and repeatable, and it preserves local journal IDs as source keys so the same entry is not imported twice. Existing Mini App reading marks stored only in a browser or Telegram CloudStorage are separate and are not included by this SQLite export.

First ensure D1 has the reading plan and apply migration `0009_journal_entries.sql` with the other migrations. Then prepare and inspect the personal-data file locally:

```powershell
python scripts/export_local_data_to_d1.py `
  --database data/daily_verse.sqlite3 `
  --output data/private_d1_import.sql
```

The output path is ignored by Git. Review the file locally; do not paste it into chat or commit it. For an existing D1 account, the import fills missing profile fields and adds missing completions and journals; it preserves current D1 reminder and leaderboard preferences. Execute it against remote D1 only after confirming that the existing users' private profiles, progress, and journal entries should be transferred:

```powershell
npx wrangler d1 execute daily-verse-aastu --remote --file=data/private_d1_import.sql
```

After confirming the import, securely delete the generated SQL file. Account deletion continues to remove a user's profile, completions, and journal entries from D1 through foreign-key cascades.

For Worker inline search, set Telegram's webhook to include `inline_query` updates only after the Worker deployment is intentionally being tested. Registered users can query references such as `Genesis 1:1`, `Psalm 23:1`, `ዘፍጥረት 1`, and `መዝሙረ ዳዊት 23:1` in any supported chat. Chapter results offer a button to open the full chapter in the Mini App. The `/today` response and selected plan days open the assigned chapters there. These links depend on the matching chapter assets being deployed at `MINI_APP_URL`.

The D1 base schema is in `cloudflare/worker/migrations/0001_schema.sql`. Later migrations add profile fields (`0003_add_display_name.sql`, `0004_add_academic_profile.sql`), reminder runs (`0005_reminder_runs.sql`), leaderboard opt-in (`0006_add_leaderboard_opt_in.sql`), profile-edit state (`0007_add_profile_edit_state.sql`), and independent reminder times (`0008_reminder_schedule_slots.sql`). The canonical reading plan is exported to `cloudflare/worker/seed/0002_reading_plan.sql`; regenerate it after an approved plan change with:

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

The Worker uses Python through Pyodide; verify package compatibility before adding Python dependencies. The local bot environment and Cloudflare Worker deployment remain separate: local SQLite edits do not update D1, and D1 changes do not rewrite local records.

English Bible text still requires a separately licensed source.
