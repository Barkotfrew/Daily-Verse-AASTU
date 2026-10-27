"""Tests for bilingual book-name lookup and reference parsing."""

import unittest

from app.references import BOOKS, ReferenceParseError, find_book, parse_reference


class BibleReferenceTests(unittest.TestCase):
    def test_mapping_covers_all_66_protestant_books(self) -> None:
        self.assertEqual(len(BOOKS), 66)
        self.assertEqual(len({book.id for book in BOOKS}), 66)

    def test_parses_english_and_amharic_examples(self) -> None:
        self.assertEqual(parse_reference("  pSaLm   23:1 ").book_id, "PSA")
        self.assertEqual(parse_reference("Genesis 1").chapter_start, 1)
        self.assertEqual(parse_reference("ዘፍጥረት 1").book_id, "GEN")
        self.assertEqual(parse_reference("ዮሐንስ 3:16").book_id, "JHN")

    def test_parses_chapter_and_verse_ranges(self) -> None:
        chapters = parse_reference("Genesis 1–3")
        verses = parse_reference("John 3:16-18")

        self.assertEqual((chapters.chapter_start, chapters.chapter_end), (1, 3))
        self.assertFalse(chapters.is_verse_reference)
        self.assertEqual((verses.verse_start, verses.verse_end), (16, 18))
        self.assertTrue(verses.is_verse_reference)

    def test_numbered_books_and_aliases_resolve(self) -> None:
        self.assertEqual(parse_reference("I Samuel 2:1").book_id, "1SA")
        self.assertEqual(parse_reference("1 ሳሙኤል 2").book_id, "1SA")
        self.assertEqual(find_book("Song of Songs").id, "SNG")

    def test_rejects_unknown_or_malformed_references(self) -> None:
        for query in ("", "NotABook 1", "John", "John zero", "John 0", "John 3:0", "John 4:2-1", "Genesis 3-1", "John 1-2:3"):
            with self.subTest(query=query):
                with self.assertRaises(ReferenceParseError):
                    parse_reference(query)


if __name__ == "__main__":
    unittest.main()
