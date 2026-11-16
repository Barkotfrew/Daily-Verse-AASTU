CREATE TABLE IF NOT EXISTS reading_sessions (
    telegram_user_id INTEGER NOT NULL,
    plan_day INTEGER NOT NULL CHECK (plan_day > 0),
    started_at INTEGER NOT NULL,
    PRIMARY KEY (telegram_user_id, plan_day),
    FOREIGN KEY (telegram_user_id) REFERENCES users (telegram_user_id) ON DELETE CASCADE
);
