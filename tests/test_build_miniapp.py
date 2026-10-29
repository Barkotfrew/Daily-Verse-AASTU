"""Tests for exporting a small, chapter-at-a-time static Mini App data set."""

import json
from pathlib import Path
import tempfile
import unittest

from app.references import BOOKS
from scripts.build_miniapp import build_site


class MiniAppBuildTests(unittest.TestCase):
    def test_build_creates_separate_chapter_assets_and_book_index(self) -> None:
        source_books = [
            {
                "title": book.amharic,
                "chapters": [{"chapter": "1", "verses": ["synthetic fixture text"]}],
            }
            for book in BOOKS
        ]
        source_books[0]["chapters"][0]["verses"].append("")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.json"
            output = root / "site"
            source.write_text(json.dumps({"books": source_books}), encoding="utf-8")

            book_count, chapter_count = build_site(source, output)

            self.assertEqual((book_count, chapter_count), (66, 66))
            index = json.loads((output / "assets" / "books.json").read_text(encoding="utf-8"))
            genesis = json.loads(
                (output / "assets" / "chapters" / "GEN" / "1.json").read_text(encoding="utf-8")
            )
            self.assertEqual(index["books"][0]["chapters"], [1])
            self.assertFalse(genesis["complete"])
            self.assertEqual(genesis["verses"][0]["text"], "synthetic fixture text")
            readings = json.loads(
                (output / "assets" / "readings.json").read_text(encoding="utf-8")
            )
            day_18 = next(entry for entry in readings["entries"] if entry["day"] == 18)
            self.assertEqual(
                [(passage["book_id"], passage["chapter"]) for passage in day_18["passages"]],
                [("GEN", 19), ("GEN", 20), ("GEN", 21)],
            )
            self.assertEqual(len(readings["entries"]), 231)
            self.assertTrue((output / "index.html").is_file())
            self.assertEqual(
                (output / "fonts" / "Benaiah.ttf").read_bytes(),
                (Path(__file__).resolve().parents[1] / "webapp" / "fonts" / "Benaiah.ttf").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
