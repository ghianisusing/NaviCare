"""
Information Service — the entry point `agents/navigator/service.py`
calls into when routing to the Information Agent.

Mirrors the shape of agents/navigator/service.py's failure handling:
agent-layer errors are caught here and turned into a safe fallback
message rather than propagating to the caller.
"""

from __future__ import annotations

import logging
import time

from agents.core.exceptions import AgentError

from .agent import InformationResult, run_information_agent

logger = logging.getLogger("agents.information")

FALLBACK_RESPONSE = "I'm having trouble processing that right now. Please try again shortly."


class InformationTurnResult:
    def __init__(self, *, response_text: str, sources: list[dict], succeeded: bool, latency_seconds: float):
        self.response_text = response_text
        self.sources = sources
        self.succeeded = succeeded
        self.latency_seconds = latency_seconds


def handle_information_request(*, conversation, question: str) -> InformationTurnResult:
    started_at = time.monotonic()

    try:
        result: InformationResult = run_information_agent(question=question)
        response_text = result.response
        sources = result.sources
        succeeded = True
    except AgentError as exc:
        response_text = FALLBACK_RESPONSE
        sources = []
        succeeded = False
        logger.warning("Information agent failed (%s): %s", type(exc).__name__, exc)

    latency_seconds = time.monotonic() - started_at

    logger.info(
        "information_turn",
        extra={
            "conversation_id": conversation.id,
            "agent_type": "information",
            "retrieval_count": len(sources),
            "success": succeeded,
            "latency_ms": round(latency_seconds * 1000),
        },
    )

    return InformationTurnResult(
        response_text=response_text, sources=sources, succeeded=succeeded, latency_seconds=latency_seconds
    )
