ALTER TABLE users ADD COLUMN leaderboard_opt_in INTEGER NOT NULL DEFAULT 0
    CHECK (leaderboard_opt_in IN (0, 1));
