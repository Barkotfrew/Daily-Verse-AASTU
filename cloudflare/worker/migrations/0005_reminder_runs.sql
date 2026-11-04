CREATE TABLE IF NOT EXISTS reminder_runs (
    reminder_date TEXT PRIMARY KEY,
    last_user_id INTEGER NOT NULL DEFAULT 0,
    finished INTEGER NOT NULL DEFAULT 0 CHECK (finished IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
