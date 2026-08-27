from django.test import TestCase

from knowledge.ingestion import ingest_document
from knowledge.models import HealthcareDocument
from knowledge.retrieval import retrieve


class RetrieveTests(TestCase):
    def setUp(self):
        doc_a = HealthcareDocument.objects.create(
            title="Fasting Before a Blood Test",
            content=(
                "Fasting before a blood test typically means not eating or drinking anything "
                "except water for 8 to 12 hours before the sample is drawn."
            ),
            source="Test Source",
            source_url="https://example.com/fasting",
            category=HealthcareDocument.Category.DIAGNOSTIC_TESTS,
        )
        doc_b = HealthcareDocument.objects.create(
            title="Types of Healthcare Providers",
            content=(
                "Primary care providers handle routine checkups. Specialists focus on a "
                "particular body system. Emergency departments handle life-threatening issues."
            ),
            source="Test Source",
            source_url="https://example.com/providers",
            category=HealthcareDocument.Category.HEALTHCARE_SERVICES,
        )
        ingest_document(doc_a)
        ingest_document(doc_b)

    def test_relevant_question_retrieves_matching_chunk(self):
        results = retrieve("What does fasting mean before a blood test?")
        self.assertGreater(len(results), 0)
        self.assertIn("Fasting", results[0].document_title)

    def test_unrelated_question_retrieves_nothing_above_threshold(self):
        results = retrieve("How do I change a flat tire on my car?")
        self.assertEqual(results, [])

    def test_results_include_source_metadata(self):
        results = retrieve("fasting before a blood test")
        self.assertGreater(len(results), 0)
        top = results[0]
        self.assertTrue(top.source)
        self.assertTrue(top.source_url)
        self.assertIsInstance(top.similarity_score, float)

    def test_results_are_ranked_by_similarity(self):
        results = retrieve("healthcare providers and specialists", top_k=5)
        scores = [r.similarity_score for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_top_k_limits_results(self):
        results = retrieve("healthcare", top_k=1)
        self.assertLessEqual(len(results), 1)
