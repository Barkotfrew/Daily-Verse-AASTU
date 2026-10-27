"""Canonical Amharic Bible data access for chapter and verse readers.

The repository expects a normalized JSON export. Provider-specific source
parsing belongs in an import step, not in Telegram handlers.
"""

from dataclasses import dataclass
import json
from pathlib import Path


class BibleDataError(ValueError):
    """Raised when Bible data cannot be loaded or is malformed."""


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
        for book in raw["books"]:
            self._load_book(book)

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
