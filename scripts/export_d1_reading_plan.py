"""Export the canonical JSON plan as idempotent SQL inserts for Cloudflare D1."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "reading_plan.json"
OUTPUT = ROOT / "cloudflare" / "worker" / "seed" / "0002_reading_plan.sql"


def sql_text(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def export_plan(source: Path = SOURCE, output: Path = OUTPUT) -> int:
    plan = json.loads(source.read_text(encoding="utf-8"))
    rows = [
        "INSERT OR REPLACE INTO reading_plan (plan_day, ethiopian_date, reading, gregorian_date) "
        f"VALUES ({day}, {sql_text(ethiopian_date)}, {sql_text(reading)}, {sql_text(gregorian_date)});"
        for day, ethiopian_date, reading, gregorian_date in plan["entries"]
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "-- Generated from data/reading_plan.json by scripts/export_d1_reading_plan.py.\n"
        + "\n".join(rows)
        + "\n",
        encoding="utf-8",
    )
    return len(rows)


if __name__ == "__main__":
    print(f"Exported {export_plan()} reading-plan entries to {OUTPUT.relative_to(ROOT)}")
