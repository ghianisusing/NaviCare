"""
A small, dependency-free text embedding function.

This is a prototype-grade embedding: a hashing-trick bag-of-words
vectorizer (hash each token into one of EMBEDDING_DIM buckets, weight by
term frequency, L2-normalize). It requires no network call and no ML
dependency, which keeps ingestion and retrieval fully offline and
deterministic — appropriate for a small curated knowledge base.

For production, swap this out for a real embedding model/API behind the
same `embed_text(text) -> list[float]` signature; nothing in
knowledge/retrieval.py or knowledge/ingestion.py needs to change beyond
this function, and DocumentChunk.embedding already stores a plain list
of floats so the dimensionality is the only migration concern.
"""

from __future__ import annotations

import hashlib
import math
import re

from decouple import config

EMBEDDING_DIM = config("EMBEDDING_DIM", default=2048, cast=int)

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

# A small, generic English stopword list. Filtering these out matters
# more than usual here because this is a bag-of-words/hashing embedding
# with no IDF weighting — without it, short documents that happen to
# share common function words (e.g. "the", "is", "a") would look
# artificially similar. This is not meant to be linguistically complete,
# just enough to keep retrieval signal on content words.
_STOPWORDS = frozenset(
    """
    a an the this that these those is are was were be been being
    of to in on for with as by at from into over under
    and or but if then than so
    it its it's he she they them his her their our your my
    i you we do does did not no
    can could should would may might will shall
    have has had
    about above after again against all am any because before below
    between both down during each few further here how just more most
    once only other out own same some such there through too very
    what why who whom which when where
    """.split()
)


def _tokenize(text: str) -> list[str]:
    tokens = _TOKEN_PATTERN.findall(text.lower())
    return [token for token in tokens if token not in _STOPWORDS]


def _hash_bucket(token: str, dim: int) -> int:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % dim


def embed_text(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Return an L2-normalized fixed-length vector for `text`.

    Empty or token-less input returns a zero vector; callers should
    treat a zero vector as "no similarity" rather than dividing by its
    (zero) norm.
    """
    vector = [0.0] * dim
    tokens = _tokenize(text)

    for token in tokens:
        bucket = _hash_bucket(token, dim)
        vector[bucket] += 1.0

    norm = math.sqrt(sum(component * component for component in vector))
    if norm == 0.0:
        return vector
    return [component / norm for component in vector]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))  # both vectors are already L2-normalized
