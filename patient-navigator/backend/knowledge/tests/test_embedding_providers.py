"""Hosted embedding providers, model tracking, and outage handling.

No test here touches the network: hosted providers are exercised with a
mocked `requests.post`, and search uses a small fake provider.
"""

import math
from unittest import mock

import requests
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from agents.core.exceptions import LLMUnavailableError
from agents.information.agent import run_information_agent
from knowledge.embeddings import (
    EmbeddingError,
    EmbeddingProvider,
    LocalHashingProvider,
    OpenAIEmbeddingProvider,
    VoyageProvider,
    get_embedding_provider,
    set_embedding_provider,
)
from knowledge.ingestion import ingest_all, ingest_document
from knowledge.models import DocumentChunk, HealthcareDocument
from knowledge.retrieval import retrieve


def _response(status_code=200, payload=None):
    response = mock.Mock(status_code=status_code)
    response.json.return_value = payload
    return response


def _rows(*vectors):
    # Deliberately out of order: providers must sort by "index".
    return {"data": [{"index": i, "embedding": v} for i, v in reversed(list(enumerate(vectors)))]}


class VoyageProviderTests(SimpleTestCase):
    def setUp(self):
        self.provider = VoyageProvider(api_key="test-key", model="voyage-4")

    @mock.patch("knowledge.embeddings.requests.post")
    def test_documents_and_queries_use_matching_input_types(self, post):
        post.return_value = _response(payload=_rows([3.0, 4.0], [0.0, 2.0]))
        vectors = self.provider.embed_documents(["first", "second"])

        body = post.call_args.kwargs["json"]
        self.assertEqual(body, {"input": ["first", "second"], "model": "voyage-4", "input_type": "document"})
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer test-key")
        # Returned in input order and L2-normalized.
        self.assertEqual(vectors, [[0.6, 0.8], [0.0, 1.0]])

        post.return_value = _response(payload=_rows([1.0, 0.0]))
        self.provider.embed_query("question")
        self.assertEqual(post.call_args.kwargs["json"]["input_type"], "query")

    @mock.patch("knowledge.embeddings.requests.post")
    def test_large_inputs_are_sent_in_batches(self, post):
        post.side_effect = lambda *a, **kw: _response(payload=_rows(*[[1.0, 0.0]] * len(kw["json"]["input"])))
        vectors = self.provider.embed_documents([f"chunk {i}" for i in range(VoyageProvider.BATCH_SIZE + 5)])
        self.assertEqual(post.call_count, 2)
        self.assertEqual(len(vectors), VoyageProvider.BATCH_SIZE + 5)

    def test_model_id_names_provider_and_model(self):
        self.assertEqual(self.provider.model_id, "voyage:voyage-4")

    def test_missing_api_key_raises_without_calling_out(self):
        with mock.patch("knowledge.embeddings.requests.post") as post:
            with self.assertRaises(EmbeddingError):
                VoyageProvider(api_key="", model="voyage-4").embed_query("hi")
            post.assert_not_called()

    @mock.patch("knowledge.embeddings.requests.post")
    def test_failures_become_embedding_errors(self, post):
        cases = [
            requests.Timeout(),
            requests.ConnectionError(),
            _response(status_code=401, payload={"detail": "secret account info"}),
            _response(status_code=503),
            _response(payload={"unexpected": True}),
            _response(payload={"data": []}),
        ]
        for case in cases:
            with self.subTest(case=case):
                post.side_effect = case if isinstance(case, Exception) else None
                post.return_value = case
                with self.assertRaises(EmbeddingError) as ctx:
                    self.provider.embed_query("question")
                self.assertNotIn("secret", str(ctx.exception))


class OpenAIEmbeddingProviderTests(SimpleTestCase):
    @mock.patch("knowledge.embeddings.requests.post")
    def test_request_shape(self, post):
        post.return_value = _response(payload=_rows([1.0, 1.0]))
        vector = OpenAIEmbeddingProvider("k", "text-embedding-3-small").embed_query("question")
        self.assertEqual(post.call_args.kwargs["json"], {"input": ["question"], "model": "text-embedding-3-small"})
        self.assertAlmostEqual(math.hypot(*vector), 1.0)


class ProviderSelectionTests(SimpleTestCase):
    def tearDown(self):
        set_embedding_provider(None)

    def _build(self, **env):
        set_embedding_provider(None)
        with mock.patch.dict("os.environ", env):
            return get_embedding_provider()

    def test_selects_provider_and_default_model(self):
        self.assertEqual(self._build(EMBEDDING_PROVIDER="voyage").model_id, "voyage:voyage-4")
        self.assertEqual(self._build(EMBEDDING_PROVIDER="openai").model_id, "openai:text-embedding-3-small")
        self.assertEqual(self._build(EMBEDDING_PROVIDER="voyage", EMBEDDING_MODEL="voyage-4-lite").model_id, "voyage:voyage-4-lite")
        self.assertIsInstance(self._build(EMBEDDING_PROVIDER="local"), LocalHashingProvider)

    def test_unknown_provider_is_rejected(self):
        with self.assertRaises(EmbeddingError):
            self._build(EMBEDDING_PROVIDER="mystery")

    def test_test_suite_runs_offline(self):
        set_embedding_provider(None)
        self.assertIsInstance(get_embedding_provider(), LocalHashingProvider)


class FakeSemanticProvider(EmbeddingProvider):
    """Maps texts to fixed directions by topic, standing in for a model
    that understands meaning: 'bloodwork' and 'fasting' share a vector
    even though they share no words."""

    model_id = "fake:semantic"
    default_min_similarity = 0.5

    def __init__(self):
        self.fail = False

    def _vector(self, text):
        text = text.lower()
        if any(word in text for word in ("fasting", "bloodwork", "eating")):
            return [1.0, 0.0]
        return [0.0, 1.0]

    def embed_documents(self, texts):
        if self.fail:
            raise EmbeddingError("down")
        return [self._vector(t) for t in texts]

    def embed_query(self, text):
        if self.fail:
            raise EmbeddingError("down")
        return self._vector(text)


class SearchWithModelTrackingTests(TestCase):
    def setUp(self):
        self.provider = FakeSemanticProvider()
        set_embedding_provider(self.provider)
        self.addCleanup(set_embedding_provider, None)
        self.document = HealthcareDocument.objects.create(
            title="Fasting Before a Blood Test",
            content="Fasting before a blood test means not eating for 8 to 12 hours.",
            source="Test Source",
            source_url="https://example.com/fasting",
            category=HealthcareDocument.Category.DIAGNOSTIC_TESTS,
        )
        ingest_document(self.document)

    def test_chunks_record_the_model_that_embedded_them(self):
        self.assertEqual(set(DocumentChunk.objects.values_list("embedding_model", flat=True)), {"fake:semantic"})

    def test_finds_answer_by_meaning_and_uses_model_threshold(self):
        results = retrieve("Do I need to stop eating before bloodwork?")
        self.assertEqual(results[0].document_title, "Fasting Before a Blood Test")
        self.assertEqual(retrieve("How do I change a tire?"), [])

    def test_chunks_from_another_model_are_never_compared(self):
        set_embedding_provider(LocalHashingProvider())
        with self.assertLogs("knowledge.retrieval", level="WARNING"):
            self.assertEqual(retrieve("fasting before a blood test"), [])

    def test_only_missing_re_embeds_documents_from_an_old_model(self):
        self.assertEqual(ingest_all(only_missing=True), {})
        set_embedding_provider(LocalHashingProvider())
        self.assertEqual(list(ingest_all(only_missing=True)), [self.document.title])
        self.assertTrue(retrieve("fasting before a blood test"))

    def test_failed_re_ingest_keeps_existing_chunks(self):
        before = list(DocumentChunk.objects.values_list("id", flat=True))
        self.document.content = "Completely new content."
        self.provider.fail = True
        with self.assertRaises(EmbeddingError):
            ingest_document(self.document)
        self.assertEqual(list(DocumentChunk.objects.values_list("id", flat=True)), before)
        self.document.refresh_from_db()
        self.assertIn("Fasting", self.document.content)

    @mock.patch("agents.information.agent.get_llm_provider")
    def test_outage_is_an_agent_failure_not_insufficient_information(self, get_llm):
        self.provider.fail = True
        with self.assertRaises(LLMUnavailableError):
            run_information_agent(question="What does fasting mean?")
        get_llm.assert_not_called()


class AdminIngestOutageTests(APITestCase):
    def setUp(self):
        provider = FakeSemanticProvider()
        provider.fail = True
        set_embedding_provider(provider)
        self.addCleanup(set_embedding_provider, None)
        admin = User.objects.create_user(username="admin", password="S0meStrongPass!", is_staff=True)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(admin).access_token}")

    def test_create_returns_503_and_saves_nothing(self):
        response = self.client.post(
            "/api/knowledge/documents/",
            {"title": "New", "content": "Some content.", "source": "S", "category": "general_health"},
            format="json",
        )
        self.assertEqual(response.status_code, 503)
        self.assertFalse(HealthcareDocument.objects.exists())

    def test_trigger_ingestion_returns_503(self):
        HealthcareDocument.objects.create(title="T", content="C.", source="S", category="general_health")
        response = self.client.post("/api/knowledge/ingest/")
        self.assertEqual(response.status_code, 503)
