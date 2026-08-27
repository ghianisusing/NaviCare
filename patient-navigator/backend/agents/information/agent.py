"""
Information Agent — answers general healthcare information questions
using retrieval-augmented generation.

Flow: patient question -> knowledge.retrieval.retrieve() -> construct
grounded context -> LLM -> validated structured output -> sources
attached from the retrieval results (never from the LLM).

If retrieval finds nothing above the similarity threshold, this module
skips the LLM call entirely and returns the fixed "insufficient
information" response — this is a deterministic guarantee against
hallucinating an answer from the model's general knowledge, not
something left to the prompt alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agents.core.llm import LLMMessage, get_llm_provider
from knowledge.retrieval import RetrievedChunk, retrieve

from .prompts import INFORMATION_SYSTEM_PROMPT, build_user_prompt
from .schemas import parse_information_output

INSUFFICIENT_INFO_RESPONSE = (
    "I don't have enough information in my healthcare knowledge base to "
    "answer that reliably. A healthcare professional can provide "
    "guidance specific to your situation."
)


@dataclass
class InformationResult:
    response: str
    has_sufficient_information: bool
    sources: list[dict] = field(default_factory=list)


def run_information_agent(*, question: str) -> InformationResult:
    """Run one Information Agent turn.

    Raises `agents.core.exceptions.AgentError` subclasses if the LLM
    call itself fails or returns unusable output — retrieval failures
    are handled internally (empty results -> deterministic fallback,
    never an exception) rather than propagating.
    """
    chunks = retrieve(question)

    if not chunks:
        return InformationResult(response=INSUFFICIENT_INFO_RESPONSE, has_sufficient_information=False, sources=[])

    retrieved_context = _format_context(chunks)
    provider = get_llm_provider()

    result = provider.complete(
        system_prompt=INFORMATION_SYSTEM_PROMPT,
        messages=[LLMMessage(role="user", content=build_user_prompt(question=question, retrieved_context=retrieved_context))],
        max_tokens=600,
        temperature=0.1,
    )

    response_text, has_sufficient_information = parse_information_output(result.text)

    sources = [] if not has_sufficient_information else _dedupe_sources(chunks)
    return InformationResult(
        response=response_text,
        has_sufficient_information=has_sufficient_information,
        sources=sources,
    )


def _format_context(chunks: list[RetrievedChunk]) -> str:
    blocks = []
    for i, chunk in enumerate(chunks, start=1):
        blocks.append(f"[{i}] Source: {chunk.document_title} ({chunk.source})\n{chunk.content}")
    return "\n\n".join(blocks)


def _dedupe_sources(chunks: list[RetrievedChunk]) -> list[dict]:
    seen = set()
    sources = []
    for chunk in chunks:
        key = (chunk.document_title, chunk.source_url)
        if key in seen:
            continue
        seen.add(key)
        sources.append({"title": chunk.document_title, "source": chunk.source, "source_url": chunk.source_url})
    return sources
