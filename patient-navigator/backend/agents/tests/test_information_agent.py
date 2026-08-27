import json
from unittest import mock

from django.test import TestCase

from agents.core.llm import LLMResult
from agents.information.agent import INSUFFICIENT_INFO_RESPONSE, run_information_agent
from knowledge.ingestion import ingest_document
from knowledge.models import HealthcareDocument


class FakeProvider:
    def __init__(self, text):
        self._text = text
        self.calls = 0

    def complete(self, **kwargs):
        self.calls += 1
        return LLMResult(text=self._text, raw={})


class RunInformationAgentTests(TestCase):
    def setUp(self):
        self.document = HealthcareDocument.objects.create(
            title="Fasting Before a Blood Test",
            content=(
                "Fasting before a blood test typically means not eating or drinking anything "
                "except water for 8 to 12 hours before the sample is drawn."
            ),
            source="Test Source",
            source_url="https://example.com/fasting",
            category=HealthcareDocument.Category.DIAGNOSTIC_TESTS,
        )
        ingest_document(self.document)

    @mock.patch("agents.information.agent.get_llm_provider")
    def test_known_question_retrieves_and_grounds_answer(self, mock_get_provider):
        mock_get_provider.return_value = FakeProvider(
            text=json.dumps(
                {
                    "response": "Fasting means avoiding food for 8-12 hours before the test.",
                    "has_sufficient_information": True,
                }
            )
        )

        result = run_information_agent(question="What does fasting mean before a blood test?")

        self.assertTrue(result.has_sufficient_information)
        self.assertIn("Fasting", result.response)
        self.assertEqual(len(result.sources), 1)
        self.assertEqual(result.sources[0]["title"], "Fasting Before a Blood Test")

    @mock.patch("agents.information.agent.get_llm_provider")
    def test_unknown_question_skips_llm_and_refuses_to_fabricate(self, mock_get_provider):
        provider = FakeProvider(text="{}")
        mock_get_provider.return_value = provider

        result = run_information_agent(question="How do I fix a flat tire on my car?")

        self.assertFalse(result.has_sufficient_information)
        self.assertEqual(result.response, INSUFFICIENT_INFO_RESPONSE)
        self.assertEqual(result.sources, [])
        # The LLM should never even be called when retrieval finds nothing.
        self.assertEqual(provider.calls, 0)

    @mock.patch("agents.information.agent.get_llm_provider")
    def test_llm_says_insufficient_despite_retrieval_hit(self, mock_get_provider):
        mock_get_provider.return_value = FakeProvider(
            text=json.dumps(
                {
                    "response": "I don't have enough information to answer that reliably.",
                    "has_sufficient_information": False,
                }
            )
        )

        result = run_information_agent(question="What does fasting mean before a blood test?")

        self.assertFalse(result.has_sufficient_information)
        # No sources attached when the agent itself says it couldn't answer.
        self.assertEqual(result.sources, [])
