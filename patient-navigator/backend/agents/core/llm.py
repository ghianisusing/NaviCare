"""
LLM provider abstraction.

Nothing outside this module should import an LLM SDK or construct an API
request directly — the Navigator Agent (and, later, any specialized
agent) depends only on the `LLMProvider` interface below, so switching
providers or models is a one-file change.

Credentials are read exclusively from environment variables:

    LLM_API_KEY=
    LLM_MODEL=
    LLM_PROVIDER=anthropic   # currently the only supported value

Nothing here logs the API key or raw request/response bodies — see
agents/core/context.py and the Navigator's own logging for what *is*
recorded.
"""

from __future__ import annotations

import abc
import json
import logging
from dataclasses import dataclass, field

import requests
from decouple import config

from .exceptions import LLMResponseError, LLMUnavailableError

logger = logging.getLogger("agents.llm")

DEFAULT_TIMEOUT_SECONDS = 20


@dataclass
class LLMMessage:
    role: str  # "user" | "assistant"
    content: str


@dataclass
class LLMResult:
    text: str
    raw: dict = field(default_factory=dict)


class LLMProvider(abc.ABC):
    """Interface every concrete provider must implement."""

    @abc.abstractmethod
    def complete(
        self,
        *,
        system_prompt: str,
        messages: list[LLMMessage],
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> LLMResult:
        """Return a single completion for the given system prompt + turns.

        Implementations must raise LLMUnavailableError on network/timeout
        failures and LLMResponseError on non-2xx / malformed responses —
        callers rely on that distinction to decide whether a retry or an
        immediate fallback response makes sense.
        """
        raise NotImplementedError


class AnthropicProvider(LLMProvider):
    """Calls the Anthropic Messages API directly over HTTPS.

    Kept dependency-free (plain `requests`) rather than pulling in the
    full SDK, since the agent layer only ever needs one endpoint.
    """

    API_URL = "https://api.anthropic.com/v1/messages"
    API_VERSION = "2023-06-01"

    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise LLMUnavailableError("LLM_API_KEY is not configured.")
        self._api_key = api_key
        self._model = model

    def complete(
        self,
        *,
        system_prompt: str,
        messages: list[LLMMessage],
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> LLMResult:
        payload = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": self.API_VERSION,
            "content-type": "application/json",
        }

        try:
            response = requests.post(
                self.API_URL,
                headers=headers,
                data=json.dumps(payload),
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
        except requests.Timeout as exc:
            raise LLMUnavailableError("LLM request timed out.") from exc
        except requests.RequestException as exc:
            raise LLMUnavailableError("LLM provider could not be reached.") from exc

        if response.status_code >= 500:
            raise LLMUnavailableError(
                f"LLM provider returned a server error ({response.status_code})."
            )
        if response.status_code >= 400:
            # Never surface the raw provider body (may contain the key's
            # account details) — just log it server-side.
            logger.warning(
                "LLM provider returned %s for a request.", response.status_code
            )
            raise LLMResponseError(
                f"LLM provider rejected the request ({response.status_code})."
            )

        try:
            data = response.json()
            text = "".join(
                block.get("text", "")
                for block in data.get("content", [])
                if block.get("type") == "text"
            )
        except (ValueError, KeyError, AttributeError) as exc:
            raise LLMResponseError(
                "LLM provider returned an unparsable response."
            ) from exc

        if not text.strip():
            raise LLMResponseError("LLM provider returned an empty completion.")

        return LLMResult(text=text, raw=data)


class OpenAIProvider(LLMProvider):
    """Calls the OpenAI Chat Completions API directly over HTTPS."""

    API_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise LLMUnavailableError("LLM_API_KEY is not configured.")
        self._api_key = api_key
        self._model = model

    def complete(
        self,
        *,
        system_prompt: str,
        messages: list[LLMMessage],
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> LLMResult:
        payload = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "system", "content": system_prompt}]
            + [{"role": m.role, "content": m.content} for m in messages],
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "content-type": "application/json",
        }

        try:
            response = requests.post(
                self.API_URL,
                headers=headers,
                data=json.dumps(payload),
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
        except requests.Timeout as exc:
            raise LLMUnavailableError("LLM request timed out.") from exc
        except requests.RequestException as exc:
            raise LLMUnavailableError("LLM provider could not be reached.") from exc

        if response.status_code >= 500:
            raise LLMUnavailableError(
                f"LLM provider returned a server error ({response.status_code})."
            )
        if response.status_code >= 400:
            logger.warning(
                "LLM provider returned %s for a request.", response.status_code
            )
            raise LLMResponseError(
                f"LLM provider rejected the request ({response.status_code})."
            )

        try:
            data = response.json()
            text = data["choices"][0]["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, AttributeError) as exc:
            raise LLMResponseError(
                "LLM provider returned an unparsable response."
            ) from exc

        if not text.strip():
            raise LLMResponseError("LLM provider returned an empty completion.")

        return LLMResult(text=text, raw=data)


_provider_instance: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    global _provider_instance
    if _provider_instance is None:
        provider_name = config("LLM_PROVIDER", default="anthropic")
        api_key = config("LLM_API_KEY", default="")
        model = config("LLM_MODEL", default=None)

        if provider_name == "anthropic":
            _provider_instance = AnthropicProvider(
                api_key=api_key, model=model or "claude-sonnet-4-6"
            )
        elif provider_name == "openai":
            _provider_instance = OpenAIProvider(
                api_key=api_key, model=model or "gpt-4o"
            )
        else:
            raise LLMUnavailableError(f"Unsupported LLM_PROVIDER: {provider_name}")
    return _provider_instance


def reset_llm_provider_cache() -> None:
    """Test helper — forces the next get_llm_provider() call to rebuild."""
    global _provider_instance
    _provider_instance = None
