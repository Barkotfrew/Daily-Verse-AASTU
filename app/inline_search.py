"""Pure inline Bible lookup logic shared by Telegram handlers and tests."""

from dataclasses import dataclass
import re

from app.bible import JsonBibleRepository, Verse
from app.references import BOOKS, ReferenceParseError, parse_reference

MAX_INLINE_RESULTS = 50
MAX_VERSE_RANGE = 50
_BOOK_BY_ID = {book.id: book for book in BOOKS}
_START_PARAMETER_RE = re.compile(r"read_([A-Z0-9]{2,3})_(\d{1,3})\Z")


@dataclass(frozen=True)
class InlineArticle:
    id: str
    title: str
    description: str
    message_text: str


@dataclass(frozen=True)
class InlineSearchResponse:
    articles: tuple[InlineArticle, ...]
    chapter_start_parameter: str | None = None


def chapter_start_parameter(book_id: str, chapter: int) -> str:
    """Create a Telegram-compatible /start payload for opening a full chapter."""
    if book_id not in _BOOK_BY_ID or not 1 <= chapter <= 999:
        raise ValueError("Invalid canonical chapter reference")
    return f"read_{book_id}_{chapter}"


def parse_chapter_start_parameter(value: str | None) -> tuple[str, int] | None:
    """Parse a validated chapter deep-link payload, returning None if malformed."""
    if not value:
        return None
    match = _START_PARAMETER_RE.fullmatch(value)
    if match is None:
        return None
    book_id, chapter = match.groups()
    if book_id not in _BOOK_BY_ID:
        return None
    chapter_number = int(chapter)
    return (book_id, chapter_number) if chapter_number > 0 else None


def _article(article_id: str, title: str, description: str, text: str) -> InlineArticle:
    if len(text) > 4096:
        raise ValueError("Inline message exceeds Telegram's text limit")
    return InlineArticle(article_id[:64], title[:256], description[:256], text)


def _help_response(
    message: str,
    chapter_parameter: str | None = None,
) -> InlineSearchResponse:
    return InlineSearchResponse((
        _article(
            "reference-help",
            "Search a Bible reference",
            "Try John 3:16 or ዮሐንስ 3:16",
            message,
        ),
    ), chapter_parameter)


def _format_verse(book_id: str, chapter: int, verse: Verse) -> str:
    book = _BOOK_BY_ID[book_id]
    return f"{book.english} {chapter}:{verse.label} · {book.amharic} {chapter}:{verse.label}\n{verse.text}"


def search_inline(query: str, bible: JsonBibleRepository | None) -> InlineSearchResponse:
    """Resolve an English or Amharic reference into concise shareable articles."""
    if not query or not query.strip():
        return _help_response("Type a Bible reference such as John 3:16 or ዮሐንስ 3:16.")
    if bible is None:
        return _help_response("Amharic Bible text is not available right now.")
    try:
        reference = parse_reference(query)
    except ReferenceParseError:
        return _help_response(
            "Reference not recognized. Try Psalm 23:1, መዝሙረ ዳዊት 23:1, or Genesis 1."
        )

    book = _BOOK_BY_ID[reference.book_id]
    if reference.is_verse_reference:
        assert reference.verse_start is not None
        verse_end = reference.verse_end or reference.verse_start
        if verse_end - reference.verse_start + 1 > MAX_VERSE_RANGE:
            return _help_response("Search a verse range of 50 verses or fewer.")
        found: list[Verse] = []
        seen: set[tuple[int, int]] = set()
        for verse_number in range(reference.verse_start, verse_end + 1):
            verse = bible.get_verse(reference.book_id, reference.chapter_start, verse_number)
            if verse is None:
                return _help_response(
                    f"Could not find {book.english} {reference.chapter_start}:{verse_number} "
                    "in the available Amharic text."
                )
            key = (verse.start, verse.end)
            if key not in seen:
                found.append(verse)
                seen.add(key)
        articles = []
        for verse in found:
            rendered = _format_verse(reference.book_id, reference.chapter_start, verse)
            if len(rendered) > 4096:
                return _help_response(
                    f"{book.english} {reference.chapter_start}:{verse.label} is too long "
                    "for one Telegram message. Open the chapter in Daily Verse instead.",
                    chapter_start_parameter(reference.book_id, reference.chapter_start),
                )
            articles.append(_article(
                f"{reference.book_id}-{reference.chapter_start}-v{verse.start}-{verse.end}",
                f"{book.english} {reference.chapter_start}:{verse.label} · {book.amharic}",
                "Amharic Bible · Select to send the verse text",
                rendered,
            ))
        return InlineSearchResponse(tuple(articles))

    if reference.chapter_start != reference.chapter_end:
        return _help_response("Search one chapter at a time, for example Genesis 1.")

    chapter_number = reference.chapter_start
    chapter = bible.get_chapter(reference.book_id, chapter_number)
    if chapter is None:
        return _help_response(f"Could not find {book.english} {chapter_number} in the available Amharic text.")
    if not chapter.complete:
        return _help_response(
            f"The available source has missing ending text for {book.english} {chapter_number}; "
            "this chapter is not shown as complete."
        )
    start_parameter = chapter_start_parameter(reference.book_id, chapter_number)
    verses = chapter.verses
    articles = []
    for verse in verses[:MAX_INLINE_RESULTS]:
        rendered = _format_verse(reference.book_id, chapter_number, verse)
        if len(rendered) > 4096:
            return _help_response(
                f"{book.english} {chapter_number}:{verse.label} is too long for one Telegram "
                "message. Open the chapter in Daily Verse instead.",
                start_parameter,
            )
        articles.append(_article(
            f"{reference.book_id}-{chapter_number}-v{verse.start}-{verse.end}",
            f"{book.english} {chapter_number}:{verse.label} · {book.amharic}",
            "Amharic Bible · Select to send the verse text",
            rendered,
        ))
    if len(verses) > MAX_INLINE_RESULTS:
        articles = articles[: MAX_INLINE_RESULTS - 1]
        articles.append(_article(
            f"{reference.book_id}-{chapter_number}-more",
            f"Open full {book.english} {chapter_number}",
            "The chapter has more verses. Use the button above to read it in Daily Verse.",
            f"Open Daily Verse and use Read Chapters for {book.english} {chapter_number}.",
        ))
    if not articles:
        return _help_response(f"No verse text is available for {book.english} {chapter_number}.")
    return InlineSearchResponse(tuple(articles), start_parameter)
