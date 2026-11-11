CREATE TABLE IF NOT EXISTS journal_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER NOT NULL,
    plan_day INTEGER CHECK (plan_day IS NULL OR plan_day > 0),
    verse_reference TEXT,
    verse_text TEXT,
    reflection TEXT NOT NULL DEFAULT '',
    prayer TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_entry_id INTEGER,
    client_entry_id TEXT,
    FOREIGN KEY (telegram_user_id) REFERENCES users (telegram_user_id) ON DELETE CASCADE,
    FOREIGN KEY (plan_day) REFERENCES reading_plan (plan_day)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_journal_source_entry
    ON journal_entries (telegram_user_id, source_entry_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_journal_client_entry
    ON journal_entries (telegram_user_id, client_entry_id);
CREATE INDEX IF NOT EXISTS idx_journal_user_recent
    ON journal_entries (telegram_user_id, created_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS journal_drafts (
    telegram_user_id INTEGER PRIMARY KEY,
    stage TEXT NOT NULL CHECK (stage IN ('day', 'reference', 'reflection', 'prayer')),
    plan_day INTEGER,
    verse_reference TEXT,
    reflection TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (telegram_user_id) REFERENCES users (telegram_user_id) ON DELETE CASCADE
);
