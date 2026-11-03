PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS reading_plan (
    plan_day INTEGER PRIMARY KEY CHECK (plan_day > 0),
    ethiopian_date TEXT NOT NULL,
    reading TEXT NOT NULL,
    gregorian_date TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS users (
    telegram_user_id INTEGER PRIMARY KEY,
    private_chat_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reminders_enabled INTEGER NOT NULL DEFAULT 1 CHECK (reminders_enabled IN (0, 1))
);

CREATE TABLE IF NOT EXISTS reading_completions (
    telegram_user_id INTEGER NOT NULL,
    plan_day INTEGER NOT NULL,
    completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (telegram_user_id, plan_day),
    FOREIGN KEY (telegram_user_id) REFERENCES users (telegram_user_id) ON DELETE CASCADE,
    FOREIGN KEY (plan_day) REFERENCES reading_plan (plan_day)
);

CREATE TABLE IF NOT EXISTS reminder_deliveries (
    reminder_date TEXT NOT NULL,
    telegram_user_id INTEGER NOT NULL,
    plan_day INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'queued', 'sent', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    last_error TEXT,
    sent_at TEXT,
    PRIMARY KEY (reminder_date, telegram_user_id),
    FOREIGN KEY (telegram_user_id) REFERENCES users (telegram_user_id) ON DELETE CASCADE,
    FOREIGN KEY (plan_day) REFERENCES reading_plan (plan_day)
);

CREATE INDEX IF NOT EXISTS idx_users_reminders
    ON users (reminders_enabled, private_chat_id);
CREATE INDEX IF NOT EXISTS idx_completions_user
    ON reading_completions (telegram_user_id, plan_day);
CREATE INDEX IF NOT EXISTS idx_reminder_pending
    ON reminder_deliveries (reminder_date, status);
