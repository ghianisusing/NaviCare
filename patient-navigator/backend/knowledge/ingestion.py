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
from .embeddings import get_embedding_provider
from .models import DocumentChunk, HealthcareDocument


def ingest_document(document: HealthcareDocument) -> int:
    """(Re-)chunk and (re-)embed a single document. Returns chunk count.

    Embeddings are fetched before anything is written, so if the
    embedding provider fails (raising EmbeddingError) the document keeps
    its existing chunks and stays searchable.
    """
    provider = get_embedding_provider()
    content = clean_text(document.content)
    chunks = chunk_text(content)
    vectors = provider.embed_documents(chunks)

    with transaction.atomic():
        document.content = content
        document.save(update_fields=["content", "updated_at"])
        DocumentChunk.objects.filter(document=document).delete()
        DocumentChunk.objects.bulk_create(
            [
                DocumentChunk(
                    document=document,
                    content=chunk_content,
                    chunk_index=index,
                    embedding=vector,
                    embedding_model=provider.model_id,
                )
                for index, (chunk_content, vector) in enumerate(zip(chunks, vectors))
            ]
        )
    return len(chunks)


def ingest_all(*, only_missing: bool = False) -> dict[str, int]:
    """Re-ingest every HealthcareDocument.

    `only_missing=True` only processes documents that have no chunks
    from the current embedding model — new documents, plus any still
    embedded by a previous model. Useful after switching
    EMBEDDING_PROVIDER/EMBEDDING_MODEL.
    """
    queryset = HealthcareDocument.objects.all()
    if only_missing:
        current_model = get_embedding_provider().model_id
        queryset = queryset.exclude(chunks__embedding_model=current_model).distinct()

    results = {}
    for document in queryset:
        results[document.title] = ingest_document(document)
    return results
