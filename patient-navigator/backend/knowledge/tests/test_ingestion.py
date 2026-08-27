from django.test import TestCase

from knowledge.ingestion import ingest_all, ingest_document
from knowledge.models import DocumentChunk, HealthcareDocument


class IngestDocumentTests(TestCase):
    def test_ingest_creates_chunks_with_embeddings(self):
        document = HealthcareDocument.objects.create(
            title="Test Document",
            content="This is the first sentence. This is the second sentence about health.",
            source="Test Source",
            category=HealthcareDocument.Category.GENERAL_HEALTH,
        )

        chunk_count = ingest_document(document)

        self.assertGreater(chunk_count, 0)
        chunks = DocumentChunk.objects.filter(document=document)
        self.assertEqual(chunks.count(), chunk_count)
        for chunk in chunks:
            self.assertTrue(len(chunk.embedding) > 0)

    def test_re_ingesting_replaces_old_chunks(self):
        document = HealthcareDocument.objects.create(
            title="Test Document",
            content="Original content here.",
            source="Test Source",
            category=HealthcareDocument.Category.GENERAL_HEALTH,
        )
        ingest_document(document)
        original_chunk_ids = set(DocumentChunk.objects.filter(document=document).values_list("id", flat=True))

        document.content = "Completely different content now, much longer than before to test replacement."
        document.save()
        ingest_document(document)

        new_chunk_ids = set(DocumentChunk.objects.filter(document=document).values_list("id", flat=True))
        self.assertTrue(original_chunk_ids.isdisjoint(new_chunk_ids))

    def test_ingest_all_processes_every_document(self):
        HealthcareDocument.objects.create(
            title="Doc A", content="Some content about doc A.", source="Source A",
            category=HealthcareDocument.Category.GENERAL_HEALTH,
        )
        HealthcareDocument.objects.create(
            title="Doc B", content="Some content about doc B.", source="Source B",
            category=HealthcareDocument.Category.SYMPTOMS,
        )

        results = ingest_all()

        self.assertEqual(set(results.keys()), {"Doc A", "Doc B"})
        self.assertEqual(DocumentChunk.objects.count(), sum(results.values()))
