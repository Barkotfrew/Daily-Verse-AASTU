"""Build the static Mini App site and one small JSON asset per Bible chapter."""

import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.bible import JsonBibleRepository
from app.references import BOOKS

SOURCE_BIBLE = ROOT / "data" / "bible" / "source" / "amharic_bible.json"
WEBAPP_SOURCE = ROOT / "webapp"
DEFAULT_OUTPUT = WEBAPP_SOURCE / "dist"


def build_site(source_bible: Path = SOURCE_BIBLE, output: Path = DEFAULT_OUTPUT) -> tuple[int, int]:
    """Build web assets, returning (book count, chapter count)."""
    bible = JsonBibleRepository(source_bible)
    output = output.resolve()
    if output.exists():
        if output != DEFAULT_OUTPUT.resolve():
            raise FileExistsError(f"Refusing to overwrite existing output directory: {output}")
        shutil.rmtree(output)
    output.mkdir(parents=True)

    for filename in ("index.html", "app.js", "style.css"):
        shutil.copy2(WEBAPP_SOURCE / filename, output / filename)

    chapter_count = 0
    books_index = []
    for book in BOOKS:
        chapter_numbers = bible.list_chapters(book.id)
        books_index.append({
            "id": book.id,
            "english": book.english,
            "amharic": book.amharic,
            "chapters": chapter_numbers,
        })
        for number in chapter_numbers:
            chapter = bible.get_chapter(book.id, number)
            chapter_path = output / "assets" / "chapters" / book.id / f"{number}.json"
            chapter_path.parent.mkdir(parents=True, exist_ok=True)
            chapter_path.write_text(
                json.dumps({
                    "book_id": chapter.book_id,
                    "book_name": chapter.book_name,
                    "number": chapter.number,
                    "complete": chapter.complete,
                    "verses": [
                        {"start": verse.start, "end": verse.end, "text": verse.text}
                        for verse in chapter.verses
                    ],
                }, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            chapter_count += 1

    assets = output / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "books.json").write_text(
        json.dumps({"language": "amharic", "books": books_index}, ensure_ascii=False),
        encoding="utf-8",
    )
    return len(books_index), chapter_count


if __name__ == "__main__":
    book_count, chapter_count = build_site()
    print(f"Built Mini App for {book_count} books and {chapter_count} available chapters.")
