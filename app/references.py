"""Bilingual Bible book names and reusable reference parsing."""

from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class Book:
    id: str
    english: str
    amharic: str
    aliases: tuple[str, ...] = ()


# Stable Protestant canon identifiers. Amharic aliases include common plan
# spellings and source-dataset book names where they differ.
BOOKS = (
    Book("GEN", "Genesis", "ዘፍጥረት"),
    Book("EXO", "Exodus", "ዘፀአት", ("ዘጸአት",)),
    Book("LEV", "Leviticus", "ዘሌዋውያን"),
    Book("NUM", "Numbers", "ዘኍልቁ", ("ዘኁልቁ",)),
    Book("DEU", "Deuteronomy", "ዘዳግም"),
    Book("JOS", "Joshua", "ኢያሱ", ("መጽሐፈ ኢያሱ ወልደ ነዌ",)),
    Book("JDG", "Judges", "መሳፍንት", ("መሣፍንት", "መጽሐፈ መሣፍንት")),
    Book("RUT", "Ruth", "ሩት", ("መጽሐፈ ሩት",)),
    Book("1SA", "1 Samuel", "1 ሳሙኤል", ("1 Samuel", "I Samuel", "First Samuel", "1ኛ ሳሙኤል", "መጽሐፈ ሳሙኤል ቀዳማዊ")),
    Book("2SA", "2 Samuel", "2 ሳሙኤል", ("2 Samuel", "II Samuel", "Second Samuel", "2ኛ ሳሙኤል", "መጽሐፈ ሳሙኤል ካልዕ")),
    Book("1KI", "1 Kings", "1 ነገሥት", ("1 Kings", "I Kings", "First Kings", "1ኛ ነገሥት", "መጽሐፈ ነገሥት ቀዳማዊ")),
    Book("2KI", "2 Kings", "2 ነገሥት", ("2 Kings", "II Kings", "Second Kings", "2ኛ ነገሥት", "መጽሐፈ ነገሥት ካልዕ")),
    Book("1CH", "1 Chronicles", "1 ዜና መዋዕል", ("1 Chronicles", "I Chronicles", "First Chronicles", "1ኛ ዜና መዋዕል", "መጽሐፈ ዜና መዋዕል ቀዳማዊ")),
    Book("2CH", "2 Chronicles", "2 ዜና መዋዕል", ("2 Chronicles", "II Chronicles", "Second Chronicles", "2ኛ ዜና መዋዕል", "መጽሐፈ ዜና መዋዕል ካልዕ")),
    Book("EZR", "Ezra", "ዕዝራ", ("መጽሐፈ ዕዝራ",)),
    Book("NEH", "Nehemiah", "ነህምያ", ("ነህምያ", "መጽሐፈ ነህምያ")),
    Book("EST", "Esther", "አስቴር", ("መጽሐፈ አስቴር",)),
    Book("JOB", "Job", "ኢዮብ", ("መጽሐፈ ኢዮብ",)),
    Book("PSA", "Psalms", "መዝሙረ ዳዊት", ("Psalm", "Psalms", "መዝሙር", "መዝሙረ ዳዊት")),
    Book("PRO", "Proverbs", "ምሳሌ", ("Proverb", "ምሳሌ ሰሎሞን")),
    Book("ECC", "Ecclesiastes", "መክብብ", ("Qoheleth",)),
    Book("SNG", "Song of Solomon", "መኃልየ መኃልይ", ("Song of Songs", "Canticles", "ማኅልየ ማኅልይ", "መኃልየ መኃልይ ዘሰሎሞን")),
    Book("ISA", "Isaiah", "ኢሳይያስ", ("ትንቢተ ኢሳይያስ",)),
    Book("JER", "Jeremiah", "ኤርምያስ", ("ትንቢተ ኤርምያስ",)),
    Book("LAM", "Lamentations", "ሰቆቃው ኤርምያስ", ("Lamentation",)),
    Book("EZK", "Ezekiel", "ሕዝቅኤል", ("ትንቢተ ሕዝቅኤል",)),
    Book("DAN", "Daniel", "ዳንኤል", ("ትንቢተ ዳንኤል",)),
    Book("HOS", "Hosea", "ሆሴዕ", ("ትንቢተ ሆሴዕ",)),
    Book("JOL", "Joel", "ኢዩኤል", ("ትንቢተ ኢዩኤል",)),
    Book("AMO", "Amos", "አሞጽ", ("ትንቢተ አሞጽ",)),
    Book("OBA", "Obadiah", "አብድዩ", ("Obadias", "ትንቢተ አብድዩ")),
    Book("JON", "Jonah", "ዮናስ", ("ትንቢተ ዮናስ",)),
    Book("MIC", "Micah", "ሚክያስ", ("ትንቢተ ሚክያስ",)),
    Book("NAM", "Nahum", "ናሆም", ("ትንቢተ ናሆም",)),
    Book("HAB", "Habakkuk", "ዕንባቆም", ("ትንቢተ ዕንባቆም",)),
    Book("ZEP", "Zephaniah", "ሶፎንያስ", ("ትንቢተ ሶፎንያስ",)),
    Book("HAG", "Haggai", "ሐጌ", ("ትንቢተ ሐጌ",)),
    Book("ZEC", "Zechariah", "ዘካርያስ", ("ትንቢተ ዘካርያስ",)),
    Book("MAL", "Malachi", "ሚልክያስ", ("ትንቢተ ሚልክያስ",)),
    Book("MAT", "Matthew", "ማቴዎስ", ("Matt", "የማቴዎስ ወንጌል")),
    Book("MRK", "Mark", "ማርቆስ", ("Mk", "የማርቆስ ወንጌል")),
    Book("LUK", "Luke", "ሉቃስ", ("Lk", "የሉቃስ ወንጌል")),
    Book("JHN", "John", "ዮሐንስ", ("Jn", "የዮሐንስ ወንጌል")),
    Book("ACT", "Acts", "የሐዋርያት ሥራ", ("Acts of the Apostles", "ሐዋርያት ሥራ")),
    Book("ROM", "Romans", "ሮሜ", ("Epistle to the Romans", "ወደ ሮሜ ሰዎች")),
    Book("1CO", "1 Corinthians", "1 ቆሮንቶስ", ("I Corinthians", "First Corinthians", "1 Cor", "1ኛ ቆሮንቶስ", "1ኛ ወደ ቆሮንቶስ ሰዎች", "ወደ ቆሮንቶስ ሰዎች")),
    Book("2CO", "2 Corinthians", "2 ቆሮንቶስ", ("II Corinthians", "Second Corinthians", "2 Cor", "2ኛ ቆሮንቶስ", "2ኛ ወደ ቆሮንቶስ ሰዎች")),
    Book("GAL", "Galatians", "ገላትያ", ("Epistle to the Galatians", "ወደ ገላትያ ሰዎች")),
    Book("EPH", "Ephesians", "ኤፌሶን", ("Epistle to the Ephesians", "ወደ ኤፌሶን ሰዎች")),
    Book("PHP", "Philippians", "ፊልጵስዩስ", ("Epistle to the Philippians", "ወደ ፊልጵስዩስ ሰዎች")),
    Book("COL", "Colossians", "ቆላስይስ", ("Epistle to the Colossians", "ወደ ቆላስይስ ሰዎች")),
    Book("1TH", "1 Thessalonians", "1 ተሰሎንቄ", ("I Thessalonians", "First Thessalonians", "1 Thess", "1ኛ ተሰሎንቄ", "1ኛ ወደ ተሰሎንቄ")),
    Book("2TH", "2 Thessalonians", "2 ተሰሎንቄ", ("II Thessalonians", "Second Thessalonians", "2 Thess", "2ኛ ተሰሎንቄ", "2ኛ ወደ ተሰሎንቄ")),
    Book("1TI", "1 Timothy", "1 ጢሞቴዎስ", ("I Timothy", "First Timothy", "1 Tim", "1ኛ ጢሞቴዎስ", "1ኛ ወደ ጢሞቴዎስ")),
    Book("2TI", "2 Timothy", "2 ጢሞቴዎስ", ("II Timothy", "Second Timothy", "2 Tim", "2ኛ ጢሞቴዎስ", "2ኛ ወደ ጢሞቴዎስ")),
    Book("TIT", "Titus", "ቲቶ", ("Epistle to Titus", "ወደ ቲቶ")),
    Book("PHM", "Philemon", "ፊልሞና", ("Philem", "Epistle to Philemon", "ወደ ፊልሞና")),
    Book("HEB", "Hebrews", "ዕብራውያን", ("Epistle to the Hebrews", "ወደ ዕብራውያን")),
    Book("JAS", "James", "ያዕቆብ", ("Epistle of James", "የያዕቆብ መልእክት")),
    Book("1PE", "1 Peter", "1 ጴጥሮስ", ("I Peter", "First Peter", "1 Pet", "1ኛ ጴጥሮስ", "1ኛ የጴጥሮስ መልእክት")),
    Book("2PE", "2 Peter", "2 ጴጥሮስ", ("II Peter", "Second Peter", "2 Pet", "2ኛ ጴጥሮስ", "2ኛ የጴጥሮስ መልእክት")),
    Book("1JN", "1 John", "1 ዮሐንስ", ("I John", "First John", "1 Jn", "1ኛ ዮሐንስ", "1ኛ የዮሐንስ መልእክት")),
    Book("2JN", "2 John", "2 ዮሐንስ", ("II John", "Second John", "2 Jn", "2ኛ ዮሐንስ", "2ኛ የዮሐንስ መልእክት")),
    Book("3JN", "3 John", "3 ዮሐንስ", ("III John", "Third John", "3 Jn", "3ኛ ዮሐንስ", "3ኛ የዮሐንስ መልእክት")),
    Book("JUD", "Jude", "ይሁዳ", ("Epistle of Jude", "የይሁዳ መልእክት")),
    Book("REV", "Revelation", "የዮሐንስ ራእይ", ("Revelations", "Apocalypse", "ራእይ")),
)


@dataclass(frozen=True)
class BibleReference:
    book_id: str
    chapter_start: int
    chapter_end: int
    verse_start: int | None = None
    verse_end: int | None = None

    @property
    def is_verse_reference(self) -> bool:
        return self.verse_start is not None


class ReferenceParseError(ValueError):
    """Raised when a query is not an unambiguous Bible reference."""


def _normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFC", value).casefold()
    value = value.replace("–", "-").replace("—", "-")
    return " ".join(value.split())


_NAME_INDEX: dict[str, Book] = {}
for _book in BOOKS:
    for _name in (_book.english, _book.amharic, *_book.aliases):
        _normalized = _normalize_name(_name)
        if _normalized in _NAME_INDEX and _NAME_INDEX[_normalized].id != _book.id:
            raise RuntimeError(f"Ambiguous Bible book alias: {_name}")
        _NAME_INDEX[_normalized] = _book

_ALIASES = sorted(_NAME_INDEX, key=len, reverse=True)
_REFERENCE_RE = re.compile(
    r"(?P<chapter>\d+)(?:\s*-\s*(?P<chapter_end>\d+))?"
    r"(?:\s*:\s*(?P<verse>\d+)(?:\s*-\s*(?P<verse_end>\d+))?)?"
)


def find_book(name: str) -> Book | None:
    """Resolve a full English or Amharic book name or known alias."""
    return _NAME_INDEX.get(_normalize_name(name))


def parse_reference(query: str) -> BibleReference:
    """Parse forms such as ``John 3:16`` or ``ዘፍጥረት 1-3``."""
    normalized = _normalize_name(query)
    if not normalized:
        raise ReferenceParseError("Enter a Bible book and chapter")

    for alias in _ALIASES:
        if not normalized.startswith(alias):
            continue
        remainder = normalized[len(alias):]
        if not remainder or not remainder[0].isspace():
            continue
        remainder = remainder.strip()
        book = _NAME_INDEX[alias]
        match = _REFERENCE_RE.fullmatch(remainder)
        if not match:
            continue
        chapter_start = int(match.group("chapter"))
        chapter_end_raw = match.group("chapter_end")
        verse_raw = match.group("verse")
        verse_end_raw = match.group("verse_end")
        chapter_end = int(chapter_end_raw) if chapter_end_raw else chapter_start
        if verse_raw is not None:
            if chapter_end_raw is not None:
                raise ReferenceParseError("Choose a chapter range or a verse range")
            verse_start = int(verse_raw)
            verse_end = int(verse_end_raw) if verse_end_raw else verse_start
            if verse_start < 1 or verse_end < verse_start:
                raise ReferenceParseError("Verse range must use positive, increasing numbers")
            if chapter_start < 1:
                raise ReferenceParseError("Chapter number must be positive")
            return BibleReference(book.id, chapter_start, chapter_start, verse_start, verse_end)
        if chapter_start < 1 or chapter_end < chapter_start:
            raise ReferenceParseError("Chapter range must use positive, increasing numbers")
        return BibleReference(book.id, chapter_start, chapter_end)

    # Distinguish a known book with malformed numbers from an unknown book.
    for alias in _ALIASES:
        if normalized.startswith(alias + " "):
            raise ReferenceParseError("Use a reference like 'John 3' or 'John 3:16'")
    raise ReferenceParseError("Unknown Bible book; check the book name")
