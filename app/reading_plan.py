"""Load and validate the shared reading plan stored in JSON."""

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path

DEFAULT_PLAN_PATH = Path(__file__).resolve().parent.parent / "data" / "reading_plan.json"


class ReadingPlanError(ValueError):
    """Raised when the shared reading plan is missing or inconsistent."""


@dataclass(frozen=True)
class ReadingEntry:
    day: int
    ethiopian_date: str
    reading: str
    gregorian_date: date


@dataclass(frozen=True)
class ReadingPlan:
    title: str
    entries: tuple[ReadingEntry, ...]

    @property
    def total_days(self) -> int:
        return len(self.entries)

    @property
    def final_day(self) -> int:
        return self.entries[-1].day

    def get_day(self, day: int) -> ReadingEntry | None:
        """Return a scheduled entry, or None outside this plan."""
        if day < 1 or day > self.final_day:
            return None
        return self.entries[day - 1]


def load_reading_plan(path: str | Path = DEFAULT_PLAN_PATH) -> ReadingPlan:
    """Read the canonical JSON plan and reject gaps, duplicates, or bad rows."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReadingPlanError(f"Could not load reading plan: {error}") from error

    if not isinstance(raw, dict):
        raise ReadingPlanError("Reading plan root must be a JSON object")
    title = raw.get("title")
    rows = raw.get("entries")
    declared_final = raw.get("final_day")
    start_date_raw = raw.get("gregorian_start_date")
    end_date_raw = raw.get("gregorian_end_date")
    if not isinstance(title, str) or not title.strip():
        raise ReadingPlanError("Reading plan title is missing")
    if not isinstance(rows, list) or not rows:
        raise ReadingPlanError("Reading plan entries must be a non-empty list")
    try:
        start_date = date.fromisoformat(start_date_raw)
        end_date = date.fromisoformat(end_date_raw)
    except (TypeError, ValueError) as error:
        raise ReadingPlanError("Gregorian start and end dates must use YYYY-MM-DD") from error

    entries: list[ReadingEntry] = []
    for index, row in enumerate(rows, start=1):
        if (
            not isinstance(row, list)
            or len(row) != 4
            or not isinstance(row[0], int)
            or isinstance(row[0], bool)
            or not isinstance(row[1], str)
            or not isinstance(row[2], str)
            or not isinstance(row[3], str)
            or not row[1].strip()
            or not row[2].strip()
        ):
            raise ReadingPlanError(f"Invalid reading plan entry at row {index}")
        if row[0] != index:
            raise ReadingPlanError(
                f"Expected day {index} at row {index}, found day {row[0]}"
            )
        try:
            gregorian_date = date.fromisoformat(row[3])
        except ValueError as error:
            raise ReadingPlanError(f"Invalid Gregorian date at row {index}") from error
        expected_date = date.fromordinal(start_date.toordinal() + index - 1)
        if gregorian_date != expected_date:
            raise ReadingPlanError(
                f"Expected Gregorian date {expected_date.isoformat()} at row {index}, "
                f"found {gregorian_date.isoformat()}"
            )
        entries.append(ReadingEntry(row[0], row[1], row[2], gregorian_date))

    if declared_final != len(entries):
        raise ReadingPlanError(
            f"final_day must equal the number of entries ({len(entries)})"
        )
    if end_date != entries[-1].gregorian_date:
        raise ReadingPlanError("gregorian_end_date must match the final entry")
    return ReadingPlan(title=title, entries=tuple(entries))
