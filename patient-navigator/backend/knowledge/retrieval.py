"""
Retrieval layer — turns a patient question into the most relevant
knowledge chunks.

Similarity is computed in Python over all active chunks rather than in
the database, since the current embedding storage is a portable
JSONField rather than an indexed vector column (see knowledge/models.py
and knowledge/embeddings.py for the trade-off and upgrade path). This
is fine at the scale of a small curated knowledge base; a real
deployment with a large corpus should move this to a proper vector
index (e.g. pgvector) instead of scanning every chunk per query.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from decouple import config

from .embeddings import cosine_similarity, get_embedding_provider
from .models import DocumentChunk

logger = logging.getLogger("knowledge.retrieval")

DEFAULT_TOP_K = config("KNOWLEDGE_RETRIEVAL_TOP_K", default=3, cast=int)

# Below this similarity, a chunk is not considered relevant enough to
# ground a response — see agents/information/agent.py, which treats an
# empty/low-similarity retrieval result as "insufficient information"
# rather than passing weak matches to the LLM as if they were reliable.
# Unset means "use the embedding model's own default", since similarity
# scores differ a lot between models.
MIN_SIMILARITY = config("KNOWLEDGE_MIN_SIMILARITY", default=None, cast=lambda v: None if v in (None, "") else float(v))


@dataclass
class RetrievedChunk:
    content: str
    similarity_score: float
    document_title: str
    source: str
    source_url: str


def retrieve(
    query: str, *, top_k: int = DEFAULT_TOP_K, min_similarity: float | None = MIN_SIMILARITY
) -> list[RetrievedChunk]:
    """Return the top_k most relevant chunks for `query`, filtered to a
    minimum similarity threshold, most relevant first.

    Raises knowledge.embeddings.EmbeddingError if the embedding provider
    fails — that's an outage, not "no relevant information".
    """
    if not query.strip():
        return []

    provider = get_embedding_provider()
    if min_similarity is None:
        min_similarity = provider.default_min_similarity

    chunks = DocumentChunk.objects.select_related("document").filter(embedding_model=provider.model_id)
    if not chunks.exists():
        if DocumentChunk.objects.exists():
            logger.warning(
                "No knowledge chunks were embedded with %s; re-run ingestion after changing the embedding model.",
                provider.model_id,
            )
        return []

    query_embedding = provider.embed_query(query)
    if not any(query_embedding):
        return []

    scored: list[RetrievedChunk] = []
    for chunk in chunks:
        score = cosine_similarity(query_embedding, chunk.embedding)
        if score >= min_similarity:
            scored.append(
                RetrievedChunk(
                    content=chunk.content,
                    similarity_score=round(score, 4),
                    document_title=chunk.document.title,
                    source=chunk.document.source,
                    source_url=chunk.document.source_url,
                )
            )

    scored.sort(key=lambda c: c.similarity_score, reverse=True)
    return scored[:top_k]
