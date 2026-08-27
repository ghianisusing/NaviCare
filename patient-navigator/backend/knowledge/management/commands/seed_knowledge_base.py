"""
Seeds (or updates) the curated development knowledge base and ingests
it (chunk + embed) in one step.

Idempotent by title: re-running updates existing documents' content
rather than creating duplicates, then re-ingests them.
"""

from django.core.management.base import BaseCommand

from knowledge.ingestion import ingest_document
from knowledge.models import HealthcareDocument
from knowledge.seed_data import get_seed_documents


class Command(BaseCommand):
    help = "Seed the healthcare knowledge base with a curated development dataset and ingest it."

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0
        total_chunks = 0

        for doc_data in get_seed_documents():
            document, created = HealthcareDocument.objects.update_or_create(
                title=doc_data["title"],
                defaults={
                    "content": doc_data["content"],
                    "source": doc_data["source"],
                    "source_url": doc_data["source_url"],
                    "category": doc_data["category"],
                },
            )
            chunk_count = ingest_document(document)
            total_chunks += chunk_count

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Knowledge base seeded: {created_count} created, {updated_count} updated, "
                f"{total_chunks} chunks embedded."
            )
        )
