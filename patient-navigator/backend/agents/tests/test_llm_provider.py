from unittest import mock

import requests
from django.test import SimpleTestCase

from agents.core.exceptions import LLMResponseError, LLMUnavailableError
from agents.core.llm import AnthropicProvider


class FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self):
        return self._json_data


class AnthropicProviderTests(SimpleTestCase):
    def setUp(self):
        self.provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-6")

    def test_missing_api_key_raises_unavailable(self):
        with self.assertRaises(LLMUnavailableError):
            AnthropicProvider(api_key="", model="claude-sonnet-4-6")

    @mock.patch("agents.core.llm.requests.post")
    def test_successful_completion_extracts_text(self, mock_post):
        mock_post.return_value = FakeResponse(
            200, {"content": [{"type": "text", "text": "hello patient"}]}
        )
        result = self.provider.complete(system_prompt="sys", messages=[])
        self.assertEqual(result.text, "hello patient")

    @mock.patch("agents.core.llm.requests.post")
    def test_timeout_raises_unavailable(self, mock_post):
        mock_post.side_effect = requests.Timeout()
        with self.assertRaises(LLMUnavailableError):
            self.provider.complete(system_prompt="sys", messages=[])

    @mock.patch("agents.core.llm.requests.post")
    def test_connection_error_raises_unavailable(self, mock_post):
        mock_post.side_effect = requests.ConnectionError()
        with self.assertRaises(LLMUnavailableError):
            self.provider.complete(system_prompt="sys", messages=[])

    @mock.patch("agents.core.llm.requests.post")
    def test_server_error_raises_unavailable(self, mock_post):
        mock_post.return_value = FakeResponse(503)
        with self.assertRaises(LLMUnavailableError):
            self.provider.complete(system_prompt="sys", messages=[])

    @mock.patch("agents.core.llm.requests.post")
    def test_client_error_raises_response_error(self, mock_post):
        mock_post.return_value = FakeResponse(401)
        with self.assertRaises(LLMResponseError):
            self.provider.complete(system_prompt="sys", messages=[])

    @mock.patch("agents.core.llm.requests.post")
    def test_empty_completion_raises_response_error(self, mock_post):
        mock_post.return_value = FakeResponse(200, {"content": [{"type": "text", "text": "   "}]})
        with self.assertRaises(LLMResponseError):
            self.provider.complete(system_prompt="sys", messages=[])

    @mock.patch("agents.core.llm.requests.post")
    def test_malformed_payload_raises_response_error(self, mock_post):
        mock_post.return_value = FakeResponse(200, {"unexpected": "shape"})
        with self.assertRaises(LLMResponseError):
            self.provider.complete(system_prompt="sys", messages=[])
