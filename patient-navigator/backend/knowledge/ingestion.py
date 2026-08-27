"""
Document ingestion pipeline:

    Document -> clean text -> split into chunks -> generate embeddings
    -> store chunks + metadata

`ingest_document` is idempotent — re-running it for a document replaces
its existing chunks rather than duplicating them, so it's safe to call
after editing a document's content.
"""

from __future__ import annotations

from django.db import transaction

from .chunking import chunk_text, clean_text
from .embeddings import embed_text
from .models import DocumentChunk, HealthcareDocument


@transaction.atomic
def ingest_document(document: HealthcareDocument) -> int:
    """(Re-)chunk and (re-)embed a single document. Returns chunk count."""
    document.content = clean_text(document.content)
    document.save(update_fields=["content", "updated_at"])

    DocumentChunk.objects.filter(document=document).delete()

    chunks = chunk_text(document.content)
    DocumentChunk.objects.bulk_create(
        [
            DocumentChunk(
                document=document,
                content=chunk_content,
                chunk_index=index,
                embedding=embed_text(chunk_content),
            )
            for index, chunk_content in enumerate(chunks)
        ]
    )
    return len(chunks)


def ingest_all(*, only_missing: bool = False) -> dict[str, int]:
    """Re-ingest every HealthcareDocument.

    `only_missing=True` skips documents that already have chunks —
    useful for a fast "fill in what's new" pass without re-embedding
    the whole knowledge base.
    """
    queryset = HealthcareDocument.objects.all()
    if only_missing:
        queryset = queryset.filter(chunks__isnull=True).distinct()

    results = {}
    for document in queryset:
        results[document.title] = ingest_document(document)
    return results
