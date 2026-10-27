"""Tests for normalized Bible data access, using synthetic fixture text only."""

from pathlib import Path
import unittest

from app.bible import JsonBibleRepository

FIXTURE = Path(__file__).parent / "fixtures" / "bible_fixture.json"


class BibleRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bible = JsonBibleRepository(FIXTURE)

    def test_returns_complete_chapter_in_verse_order(self) -> None:
        chapter = self.bible.get_chapter("genesis", 1)

        self.assertIsNotNone(chapter)
        self.assertEqual([verse.label for verse in chapter.verses], ["1", "2-3"])
        self.assertIn("not scripture", chapter.verses[0].text)

    def test_combined_verse_number_resolves_to_range_without_fabricating_text(self) -> None:
        verse_two = self.bible.get_verse("genesis", 1, 2)
        verse_three = self.bible.get_verse("genesis", 1, 3)

        self.assertEqual(verse_two, verse_three)
        self.assertEqual(verse_two.label, "2-3")

    def test_missing_chapter_or_verse_returns_none(self) -> None:
        self.assertIsNone(self.bible.get_chapter("genesis", 3))
        self.assertIsNone(self.bible.get_verse("genesis", 1, 4))
        self.assertIsNone(self.bible.get_chapter("unknown", 1))


if __name__ == "__main__":
    unittest.main()
