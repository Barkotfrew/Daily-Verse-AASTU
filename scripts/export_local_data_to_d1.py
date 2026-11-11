"""Create a private, idempotent SQL import for bot SQLite data to Cloudflare D1.

This script only reads a local SQLite file and writes a SQL file. It never
connects to Cloudflare or executes the generated statements.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Any


def sql_value(value: Any) -> str:
    """Return a safely quoted SQL literal for SQLite/D1 text and scalar values."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def fetch_rows(connection: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    return list(connection.execute(query))


def export_local_data(database: Path, output: Path) -> tuple[int, int, int]:
    """Write a merge-only D1 SQL file without exposing records in console output."""
    if not database.is_file():
        raise FileNotFoundError(f"Local SQLite database does not exist: {database}")
    database_uri = database.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(database_uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        users = fetch_rows(
            connection,
            "SELECT telegram_user_id, created_at, private_chat_id, display_name, "
            "academic_year, department, reminders_enabled, leaderboard_opt_in "
            "FROM users ORDER BY telegram_user_id",
        )
        completions = fetch_rows(
            connection,
            "SELECT telegram_user_id, plan_day, completed_at "
            "FROM reading_completions ORDER BY telegram_user_id, plan_day",
        )
        journals = fetch_rows(
            connection,
            "SELECT id, telegram_user_id, plan_day, verse_reference, reflection, prayer, created_at "
            "FROM journal_entries ORDER BY id",
        )

    statements = [
        "-- Generated from local SQLite by scripts/export_local_data_to_d1.py.",
        "-- Contains private profile data, reading history, and journal entries.",
        "-- Merge-only and repeatable: no DELETE or replacement of D1-only records.",
        "-- Apply migration 0009_journal_entries.sql before executing this file.",
        "",
    ]
    for row in users:
        values = ", ".join(
            sql_value(row[column])
            for column in (
                "telegram_user_id", "created_at", "private_chat_id", "display_name",
                "academic_year", "department", "reminders_enabled", "leaderboard_opt_in",
            )
        )
        statements.append(
            "INSERT INTO users (telegram_user_id, created_at, private_chat_id, display_name, "
            "academic_year, department, reminders_enabled, leaderboard_opt_in) "
            f"VALUES ({values}) ON CONFLICT(telegram_user_id) DO UPDATE SET "
            "private_chat_id = COALESCE(users.private_chat_id, excluded.private_chat_id), "
            "display_name = COALESCE(users.display_name, excluded.display_name), "
            "academic_year = COALESCE(users.academic_year, excluded.academic_year), "
            "department = COALESCE(users.department, excluded.department);"
        )

    for row in completions:
        values = ", ".join(
            sql_value(row[column]) for column in ("telegram_user_id", "plan_day", "completed_at")
        )
        statements.append(
            "INSERT OR IGNORE INTO reading_completions "
            f"(telegram_user_id, plan_day, completed_at) VALUES ({values});"
        )

    for row in journals:
        values = ", ".join(
            sql_value(row[column])
            for column in (
                "telegram_user_id", "plan_day", "verse_reference", "reflection", "prayer", "created_at",
            )
        )
        statements.append(
            "INSERT OR IGNORE INTO journal_entries "
            "(telegram_user_id, plan_day, verse_reference, reflection, prayer, created_at, source_entry_id) "
            f"VALUES ({values}, {sql_value(row['id'])});"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(statements) + "\n", encoding="utf-8")
    return len(users), len(completions), len(journals)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True, help="Local bot SQLite database")
    parser.add_argument(
        "--output", type=Path, required=True,
        help="Private SQL output path (for example data/private_d1_import.sql)",
    )
    args = parser.parse_args()
    user_count, completion_count, journal_count = export_local_data(args.database, args.output)
    print(
        "Prepared a private D1 import file: "
        f"{user_count} profiles, {completion_count} completions, {journal_count} journal entries."
    )
    print(f"Output: {args.output}")
    print("Review this file before any remote execution; it contains personal data.")


if __name__ == "__main__":
    main()
