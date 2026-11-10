DROP INDEX IF EXISTS idx_reminder_pending;

ALTER TABLE reminder_runs RENAME TO reminder_runs_legacy;
ALTER TABLE reminder_deliveries RENAME TO reminder_deliveries_legacy;

CREATE TABLE reminder_runs (
    reminder_date TEXT NOT NULL,
    schedule_slot TEXT NOT NULL CHECK (schedule_slot IN ('06:00', '12:00', '18:00')),
    last_user_id INTEGER NOT NULL DEFAULT 0,
    finished INTEGER NOT NULL DEFAULT 0 CHECK (finished IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (reminder_date, schedule_slot)
);

CREATE TABLE reminder_deliveries (
    reminder_date TEXT NOT NULL,
    schedule_slot TEXT NOT NULL CHECK (schedule_slot IN ('06:00', '12:00', '18:00')),
    telegram_user_id INTEGER NOT NULL,
    plan_day INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'queued', 'sent', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    last_error TEXT,
    sent_at TEXT,
    PRIMARY KEY (reminder_date, schedule_slot, telegram_user_id),
    FOREIGN KEY (telegram_user_id) REFERENCES users (telegram_user_id) ON DELETE CASCADE,
    FOREIGN KEY (plan_day) REFERENCES reading_plan (plan_day)
);

-- Preserve existing daily deliveries and runs as the first (06:00 EAT) slot.
INSERT INTO reminder_runs
    (reminder_date, schedule_slot, last_user_id, finished, created_at)
SELECT reminder_date, '06:00', last_user_id, finished, created_at
FROM reminder_runs_legacy;

INSERT INTO reminder_deliveries
    (reminder_date, schedule_slot, telegram_user_id, plan_day, status,
     attempts, last_error, sent_at)
SELECT reminder_date, '06:00', telegram_user_id, plan_day, status,
       attempts, last_error, sent_at
FROM reminder_deliveries_legacy;

DROP TABLE reminder_deliveries_legacy;
DROP TABLE reminder_runs_legacy;

CREATE INDEX idx_reminder_pending
    ON reminder_deliveries (reminder_date, schedule_slot, status);

