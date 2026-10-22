"""
Text embeddings for the knowledge base.

Search compares the meaning of a patient's question with the meaning of
each knowledge chunk, so "stop eating before bloodwork" can find an
article about "fasting before a blood test" even though they share no
words. That needs a real embedding model, called through a provider:

    EMBEDDING_PROVIDER=voyage    # voyage | openai | local
    EMBEDDING_API_KEY=
    EMBEDDING_MODEL=             # optional; each provider has a default

- `voyage`  — Voyage AI, the embedding provider Anthropic recommends
  (Anthropic has no embedding API of its own).
- `openai`  — OpenAI's embedding API.
- `local`   — the original word-hashing vectorizer. Offline and
  deterministic, but it only matches shared words, not meaning. It's
  the default so tests and CI run without a network or API key.

Every provider exposes a `model_id`. Ingestion stores it on each chunk
and retrieval only compares chunks made by the current model, because
vectors from two different models aren't comparable. After switching
provider or model, re-run ingestion (`manage.py seed_knowledge_base` or
POST /api/knowledge/ingest/).

Like agents/core/llm.py, providers use plain `requests` and never log
the API key or the text being embedded.
"""

from __future__ import annotations

import abc
import hashlib
import logging
import math
import re

import requests
from decouple import config

logger = logging.getLogger("knowledge.embeddings")

EMBEDDING_DIM = config("EMBEDDING_DIM", default=2048, cast=int)
REQUEST_TIMEOUT_SECONDS = 20


class EmbeddingError(Exception):
    """The embedding provider couldn't produce vectors (not configured,
    unreachable, timed out, or returned something unusable)."""


class EmbeddingProvider(abc.ABC):
    model_id: str
    # Below this cosine similarity a chunk isn't treated as relevant.
    # Scores aren't comparable across models, so each has its own
    # default; KNOWLEDGE_MIN_SIMILARITY overrides it.
    default_min_similarity: float

    @abc.abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed knowledge-base chunks, one vector per text, in order."""

    @abc.abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Embed a patient question for searching."""


# ---------------------------------------------------------------------------
# Local word-hashing vectorizer (offline fallback)
# ---------------------------------------------------------------------------

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

# Common words carry no topic signal, and without IDF weighting they'd
# make unrelated short texts look similar.
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
    """Word-hashing vector for `text`, L2-normalized.

    Empty or token-less input returns a zero vector; callers treat that
    as "no similarity".
    """
    vector = [0.0] * dim
    for token in _tokenize(text):
        vector[_hash_bucket(token, dim)] += 1.0

    norm = math.sqrt(sum(component * component for component in vector))
    if norm == 0.0:
        return vector
    return [component / norm for component in vector]


class LocalHashingProvider(EmbeddingProvider):
    default_min_similarity = 0.15

    def __init__(self, dim: int = EMBEDDING_DIM):
        self._dim = dim
        self.model_id = f"local-hash-{dim}"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [embed_text(text, self._dim) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return embed_text(text, self._dim)


# ---------------------------------------------------------------------------
# Hosted embedding models
# ---------------------------------------------------------------------------


class _HTTPEmbeddingProvider(EmbeddingProvider):
    """Shared request/response handling for embedding APIs that take a
    list of texts and return `{"data": [{"index", "embedding"}, ...]}`."""

    API_URL: str
    PROVIDER_NAME: str
    BATCH_SIZE = 64

    def __init__(self, api_key: str, model: str):
        self._api_key = api_key
        self._model = model
        self.model_id = f"{self.PROVIDER_NAME}:{model}"

    def _payload(self, texts: list[str], input_type: str) -> dict:
        raise NotImplementedError

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.BATCH_SIZE):
            vectors.extend(self._embed(texts[start : start + self.BATCH_SIZE], "document"))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "query")[0]

    def _embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        if not texts:
            return []
        if not self._api_key:
            raise EmbeddingError("EMBEDDING_API_KEY is not configured.")

        try:
            response = requests.post(
                self.API_URL,
                headers={"Authorization": f"Bearer {self._api_key}", "content-type": "application/json"},
                json=self._payload(texts, input_type),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.Timeout as exc:
            raise EmbeddingError("Embedding request timed out.") from exc
        except requests.RequestException as exc:
            raise EmbeddingError("Embedding provider could not be reached.") from exc

        if response.status_code >= 400:
            # Never surface the provider's body — only the status code.
            logger.warning("Embedding provider %s returned %s.", self.PROVIDER_NAME, response.status_code)
            raise EmbeddingError(f"Embedding provider returned an error ({response.status_code}).")

        try:
            rows = sorted(response.json()["data"], key=lambda row: row["index"])
            vectors = [_normalize([float(x) for x in row["embedding"]]) for row in rows]
        except (ValueError, KeyError, TypeError) as exc:
            raise EmbeddingError("Embedding provider returned an unparsable response.") from exc

        if len(vectors) != len(texts) or not all(vectors):
            raise EmbeddingError("Embedding provider returned the wrong number of vectors.")
        return vectors


class VoyageProvider(_HTTPEmbeddingProvider):
    API_URL = "https://api.voyageai.com/v1/embeddings"
    PROVIDER_NAME = "voyage"
    DEFAULT_MODEL = "voyage-4"
    # Starting point, not a calibrated value: tune it against real
    # questions with `manage.py shell` and knowledge.retrieval.retrieve.
    default_min_similarity = 0.4

    def _payload(self, texts: list[str], input_type: str) -> dict:
        # Voyage embeds questions and documents slightly differently,
        # which improves search quality.
        return {"input": texts, "model": self._model, "input_type": input_type}


class OpenAIEmbeddingProvider(_HTTPEmbeddingProvider):
    API_URL = "https://api.openai.com/v1/embeddings"
    PROVIDER_NAME = "openai"
    DEFAULT_MODEL = "text-embedding-3-small"
    default_min_similarity = 0.3  # starting point; tune as for Voyage

    def _payload(self, texts: list[str], input_type: str) -> dict:
        return {"input": texts, "model": self._model}


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------

_provider_instance: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    global _provider_instance
    if _provider_instance is None:
        name = config("EMBEDDING_PROVIDER", default="local").strip().lower()
        api_key = config("EMBEDDING_API_KEY", default="")
        model = config("EMBEDDING_MODEL", default="")

        if name == "local":
            _provider_instance = LocalHashingProvider()
        elif name == "voyage":
            _provider_instance = VoyageProvider(api_key, model or VoyageProvider.DEFAULT_MODEL)
        elif name == "openai":
            _provider_instance = OpenAIEmbeddingProvider(api_key, model or OpenAIEmbeddingProvider.DEFAULT_MODEL)
        else:
            raise EmbeddingError(f"Unsupported EMBEDDING_PROVIDER: {name}")
    return _provider_instance


def set_embedding_provider(provider: EmbeddingProvider | None) -> None:
    """Swap the provider (tests), or pass None to rebuild from settings."""
    global _provider_instance
    _provider_instance = provider


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0.0:
        return []
    return [x / norm for x in vector]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))  # both vectors are already L2-normalized
