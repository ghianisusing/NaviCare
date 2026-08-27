from django.test import SimpleTestCase

from knowledge.embeddings import cosine_similarity, embed_text


class EmbedTextTests(SimpleTestCase):
    def test_empty_text_returns_zero_vector(self):
        vector = embed_text("")
        self.assertTrue(all(component == 0.0 for component in vector))

    def test_vector_is_l2_normalized(self):
        vector = embed_text("blood pressure fasting glucose test")
        norm_squared = sum(component * component for component in vector)
        self.assertAlmostEqual(norm_squared, 1.0, places=5)

    def test_same_text_produces_same_vector(self):
        self.assertEqual(embed_text("fasting blood test"), embed_text("fasting blood test"))

    def test_dimension_matches_requested(self):
        vector = embed_text("some text", dim=64)
        self.assertEqual(len(vector), 64)


class CosineSimilarityTests(SimpleTestCase):
    def test_identical_text_has_high_similarity(self):
        a = embed_text("What does fasting before a blood test mean?")
        b = embed_text("What does fasting before a blood test mean?")
        self.assertAlmostEqual(cosine_similarity(a, b), 1.0, places=5)

    def test_related_text_has_positive_similarity(self):
        a = embed_text("fasting before a blood test")
        b = embed_text("blood test fasting requirements")
        self.assertGreater(cosine_similarity(a, b), 0.2)

    def test_unrelated_text_has_low_similarity(self):
        a = embed_text("fasting before a blood test")
        b = embed_text("how to fix a car engine")
        self.assertLess(cosine_similarity(a, b), 0.2)

    def test_mismatched_dimensions_return_zero(self):
        self.assertEqual(cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]), 0.0)

    def test_empty_vectors_return_zero(self):
        self.assertEqual(cosine_similarity([], []), 0.0)
