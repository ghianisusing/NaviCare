from django.test import SimpleTestCase

from knowledge.chunking import chunk_text, clean_text


class CleanTextTests(SimpleTestCase):
    def test_collapses_whitespace(self):
        self.assertEqual(clean_text("hello   \n\n  world"), "hello world")

    def test_strips_leading_trailing_whitespace(self):
        self.assertEqual(clean_text("  hello world  "), "hello world")


class ChunkTextTests(SimpleTestCase):
    def test_empty_text_returns_no_chunks(self):
        self.assertEqual(chunk_text(""), [])
        self.assertEqual(chunk_text("   "), [])

    def test_short_text_returns_single_chunk(self):
        chunks = chunk_text("This is a short sentence.", chunk_size=800, chunk_overlap=100)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], "This is a short sentence.")

    def test_long_text_split_into_multiple_chunks(self):
        sentence = "This is one sentence about health information. "
        long_text = sentence * 40  # well over any reasonable chunk_size
        chunks = chunk_text(long_text, chunk_size=200, chunk_overlap=40)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            # Some slack allowed for the hard-split fallback path.
            self.assertLessEqual(len(chunk), 250)

    def test_overlap_must_be_smaller_than_chunk_size(self):
        with self.assertRaises(ValueError):
            chunk_text("some text", chunk_size=100, chunk_overlap=100)

    def test_no_content_lost_across_chunks(self):
        # Every sentence should appear somewhere in the chunked output.
        text = "Alpha sentence here. Beta sentence here. Gamma sentence here."
        chunks = chunk_text(text, chunk_size=40, chunk_overlap=10)
        joined = " ".join(chunks)
        for fragment in ["Alpha sentence", "Beta sentence", "Gamma sentence"]:
            self.assertIn(fragment, joined)
