"""
Text chunking for document ingestion.

Chunk size/overlap are configurable via environment variables rather
than hardcoded, per the Phase 3 requirement — see .env.example.
"""

from __future__ import annotations

import re

from decouple import config

CHUNK_SIZE = config("KNOWLEDGE_CHUNK_SIZE", default=800, cast=int)  # characters
CHUNK_OVERLAP = config("KNOWLEDGE_CHUNK_OVERLAP", default=150, cast=int)  # characters

_WHITESPACE_RE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """Collapse whitespace and strip — ingestion should never store
    documents with irregular formatting artifacts."""
    return _WHITESPACE_RE.sub(" ", text).strip()


def chunk_text(text: str, *, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split cleaned text into overlapping, sentence-boundary-aware chunks.

    Splits on sentence boundaries first so chunks don't cut a sentence
    in half where avoidable, then packs sentences into `chunk_size`
    windows with `chunk_overlap` characters of repeated context between
    consecutive chunks.
    """
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    cleaned = clean_text(text)
    if not cleaned:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", cleaned)

    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)
            # Carry the tail of the previous chunk forward as overlap.
            tail = current[-chunk_overlap:] if chunk_overlap > 0 else ""
            current = f"{tail} {sentence}".strip()
        else:
            # A single sentence longer than chunk_size — hard-split it.
            for start in range(0, len(sentence), chunk_size - chunk_overlap):
                chunks.append(sentence[start : start + chunk_size])
            current = ""

    if current:
        chunks.append(current)

    return chunks
