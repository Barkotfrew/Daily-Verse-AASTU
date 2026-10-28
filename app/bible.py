"""Canonical Amharic Bible data access for chapter and verse readers.

The repository expects a normalized JSON export. Provider-specific source
parsing belongs in an import step, not in Telegram handlers.
"""

from dataclasses import dataclass
import json
from pathlib import Path

from app.references import BOOKS


class BibleDataError(ValueError):
    """Raised when Bible data cannot be loaded or is malformed."""


class MessageLimitError(ValueError):
    """Raised when the message limit cannot fit a reference header and verse label."""


@dataclass(frozen=True)
class Verse:
    start: int
    end: int
    text: str

    @property
    def label(self) -> str:
        return str(self.start) if self.start == self.end else f"{self.start}-{self.end}"


@dataclass(frozen=True)
class Chapter:
    book_id: str
    book_name: str
    number: int
    verses: tuple[Verse, ...]
    complete: bool = True


class JsonBibleRepository:
    """Read normalized, local JSON data using canonical book identifiers."""

    def __init__(self, path: str | Path):
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise BibleDataError(f"Could not load Bible data: {error}") from error
        if not isinstance(raw, dict) or not isinstance(raw.get("books"), list):
            raise BibleDataError("Bible data must contain a books list")

        self._chapters: dict[tuple[str, int], Chapter] = {}
        if all(isinstance(book, dict) and {"id", "name"} <= book.keys() for book in raw["books"]):
            for book in raw["books"]:
                self._load_book(book)
        elif all(isinstance(book, dict) and {"title", "chapters"} <= book.keys() for book in raw["books"]):
            self._load_amharic_source(raw["books"])
        else:
            raise BibleDataError("Unrecognized Bible books schema")

    def _load_amharic_source(self, books: list[object]) -> None:
        """Load magna25's source layout, whose book order follows the Protestant canon.

        Empty verse slots preceding text encode one combined verse range. Trailing
        empty slots have no recoverable text, so the chapter is flagged incomplete.
        """
        if len(books) != len(BOOKS):
            raise BibleDataError(
                f"Expected {len(BOOKS)} books in the Amharic source; found {len(books)}"
            )
        for book, canonical in zip(books, BOOKS, strict=True):
            if not isinstance(book, dict) or not isinstance(book.get("chapters"), list):
                raise BibleDataError("Invalid book in Amharic source data")
            for raw_chapter in book["chapters"]:
                if not isinstance(raw_chapter, dict):
                    raise BibleDataError(f"Invalid chapter in {canonical.id}")
                number = raw_chapter.get("chapter")
                rows = raw_chapter.get("verses")
                if isinstance(number, str) and number.isdecimal():
                    number = int(number)
                if not isinstance(rows, list) or not rows:
                    raise BibleDataError(f"Invalid chapter data in {canonical.id}")
                # Preserve a malformed source label as unavailable instead of
                # guessing which chapter its text belongs to.
                if not isinstance(number, int) or isinstance(number, bool) or number < 1:
                    continue

                verses: list[Verse] = []
                pending_start: int | None = None
                for index, text in enumerate(rows, start=1):
                    if not isinstance(text, str):
                        raise BibleDataError(f"Invalid verse in {canonical.id} chapter {number}")
                    if not text.strip():
                        if pending_start is None:
                            pending_start = index
                        continue
                    start = pending_start if pending_start is not None else index
                    verses.append(Verse(start, index, text))
                    pending_start = None
                chapter = Chapter(
                    canonical.id,
                    canonical.amharic,
                    number,
                    tuple(verses),
                    complete=pending_start is None,
                )
                key = (canonical.id, number)
                if key in self._chapters:
                    raise BibleDataError(f"Duplicate chapter {canonical.id} {number}")
                self._chapters[key] = chapter

    def _load_book(self, book: object) -> None:
        if not isinstance(book, dict):
            raise BibleDataError("Each book must be an object")
        book_id = book.get("id")
        book_name = book.get("name")
        chapters = book.get("chapters")
        if not isinstance(book_id, str) or not book_id.strip():
            raise BibleDataError("Book is missing its canonical id")
        if not isinstance(book_name, str) or not book_name.strip():
            raise BibleDataError(f"Book {book_id} is missing its display name")
        if not isinstance(chapters, list) or not chapters:
            raise BibleDataError(f"Book {book_id} has no chapter data")

        for chapter in chapters:
            if not isinstance(chapter, dict):
                raise BibleDataError(f"Invalid chapter in {book_id}")
            number = chapter.get("number")
            rows = chapter.get("verses")
            if not isinstance(number, int) or isinstance(number, bool) or number < 1:
                raise BibleDataError(f"Invalid chapter number in {book_id}")
            if not isinstance(rows, list) or not rows:
                raise BibleDataError(f"{book_id} chapter {number} has no verses")

            verses: list[Verse] = []
            for row in rows:
                if not isinstance(row, dict):
                    raise BibleDataError(f"Invalid verse in {book_id} chapter {number}")
                start = row.get("start")
                end = row.get("end", start)
                text = row.get("text")
                if (
                    not isinstance(start, int)
                    or isinstance(start, bool)
                    or not isinstance(end, int)
                    or isinstance(end, bool)
                    or start < 1
                    or end < start
                    or not isinstance(text, str)
                    or not text.strip()
                ):
                    raise BibleDataError(f"Invalid verse data in {book_id} chapter {number}")
                verses.append(Verse(start, end, text))

            verses.sort(key=lambda verse: verse.start)
            for previous, current in zip(verses, verses[1:]):
                if current.start <= previous.end:
                    raise BibleDataError(
                        f"Overlapping verse ranges in {book_id} chapter {number}"
                    )
            key = (book_id, number)
            if key in self._chapters:
                raise BibleDataError(f"Duplicate chapter {book_id} {number}")
            self._chapters[key] = Chapter(book_id, book_name, number, tuple(verses))

    def get_chapter(self, book_id: str, chapter_number: int) -> Chapter | None:
        """Return a complete chapter, or None when the requested data is absent."""
        return self._chapters.get((book_id, chapter_number))

    def get_verse(self, book_id: str, chapter_number: int, verse_number: int) -> Verse | None:
        """Return the actual verse row, including a combined-number row if applicable."""
        chapter = self.get_chapter(book_id, chapter_number)
        if chapter is None:
            return None
        return next(
            (verse for verse in chapter.verses if verse.start <= verse_number <= verse.end),
            None,
        )


def _split_text(text: str, limit: int) -> tuple[str, str]:
    """Split text without dropping characters, preferring a whitespace boundary."""
    if limit < 1:
        raise MessageLimitError("Message limit is too small for the verse label")
    if len(text) <= limit:
        return text, ""
    split_at = text.rfind(" ", 0, limit + 1)
    if split_at <= 0:
        split_at = limit
    else:
        split_at += 1
    return text[:split_at], text[split_at:]


def format_chapter_messages(chapter: Chapter, max_chars: int = 4000) -> tuple[str, ...]:
    """Render all verses in order, splitting only when needed and repeating references."""
    header = f"{chapter.book_name} {chapter.number}"
    if max_chars <= len(header) + 4:
        raise MessageLimitError("Message limit is too small for the chapter reference")

    messages: list[str] = []
    current_lines = [header]
    current_length = len(header)

    def flush() -> None:
        nonlocal current_lines, current_length
        if len(current_lines) > 1:
            messages.append("\n".join(current_lines))
        current_lines = [header]
        current_length = len(header)

    for verse in chapter.verses:
        remaining = verse.text
        continuation = False
        while remaining:
            label = f"{verse.label}{' (continued)' if continuation else ''}. "
            # Keep a whole verse together when it fits in a fresh message.
            fresh_capacity = max_chars - len(header) - 1 - len(label)
            if len(remaining) <= fresh_capacity:
                line = label + remaining
                if current_length + 1 + len(line) > max_chars:
                    flush()
                current_lines.append(line)
                current_length += 1 + len(line)
                break

            if len(current_lines) > 1:
                flush()
                continue

            piece, remaining = _split_text(remaining, fresh_capacity)
            line = label + piece
            current_lines.append(line)
            current_length += 1 + len(line)
            flush()
            continuation = True

    flush()
    return tuple(messages)
