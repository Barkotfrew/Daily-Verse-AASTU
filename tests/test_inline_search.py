"""Tests for bilingual inline Bible lookup with synthetic fixture text."""

from pathlib import Path
import json
import tempfile
import unittest

from app.bible import JsonBibleRepository
from app.inline_search import (
    chapter_start_parameter,
    parse_chapter_start_parameter,
    search_inline,
)

FIXTURE = Path(__file__).parent / "fixtures" / "bible_fixture.json"


class InlineSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["books"][0]["id"] = "GEN"
        payload["books"][0]["name"] = "ዘፍጥረት"
        self.temp_directory = tempfile.TemporaryDirectory()
        fixture_path = Path(self.temp_directory.name) / "canonical_fixture.json"
        fixture_path.write_text(json.dumps(payload), encoding="utf-8")
        self.bible = JsonBibleRepository(fixture_path)

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def test_english_verse_query_returns_actual_fixture_text_and_clear_language(self) -> None:
        response = search_inline("Genesis 1:1", self.bible)

        self.assertEqual(len(response.articles), 1)
        self.assertIn("Genesis 1:1", response.articles[0].title)
        self.assertIn("Amharic Bible", response.articles[0].description)
        self.assertIn("not scripture", response.articles[0].message_text)

    def test_amharic_chapter_query_returns_verse_results_and_full_chapter_link(self) -> None:
        response = search_inline("ዘፍጥረት 1", self.bible)

        self.assertEqual([item.title.split(":")[-1].split()[0] for item in response.articles], ["1", "2-3"])
        self.assertEqual(response.chapter_start_parameter, "read_GEN_1")
        self.assertEqual(
            parse_chapter_start_parameter(response.chapter_start_parameter),
            ("GEN", 1),
        )

    def test_combined_verse_slot_is_returned_once_for_either_number(self) -> None:
        two = search_inline("Genesis 1:2", self.bible)
        two_to_three = search_inline("Genesis 1:2-3", self.bible)

        self.assertEqual(len(two.articles), 1)
        self.assertEqual(len(two_to_three.articles), 1)
        self.assertIn("1:2-3", two.articles[0].title)

    def test_unknown_malformed_empty_and_unavailable_references_are_graceful(self) -> None:
        for query in ("", "NotABook 3:16", "John xyz", "John 3:999"):
            with self.subTest(query=query):
                self.assertTrue(search_inline(query, self.bible).articles)
        self.assertIn("not available", search_inline("Genesis 1:1", None).articles[0].message_text)

    def test_chapter_deep_link_rejects_invalid_payloads(self) -> None:
        self.assertEqual(chapter_start_parameter("1SA", 3), "read_1SA_3")
        self.assertIsNone(parse_chapter_start_parameter("read_INVALID_3"))
        self.assertIsNone(parse_chapter_start_parameter("read_GEN_0"))
        self.assertIsNone(parse_chapter_start_parameter("read_GEN_1?x"))


if __name__ == "__main__":
    unittest.main()
