"""
A small, synchronous tracing helper — see the module docstring on
observability/models.py for what does and doesn't get recorded.

Usage (see agents/navigator/service.py):

    tracer = Tracer(conversation=conversation, patient=patient)
    with tracer.step("navigator", "classify_intent") as step:
        ... do the work ...
        step.metadata["intent"] = agent_output.intent
    tracer.finish(status="completed", final_agent="information")

Kept deliberately lightweight — a handful of small row writes per turn,
not a payload-heavy logging pipeline. Phase 6's performance guidance
notes that in a deployment with an async task queue, persisting trace
data could be moved off the request path entirely; this project has no
such queue (see notifications/tasks.py's docstring for the same
constraint applied to background reminders), so writes happen inline
but stay intentionally small.
"""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager

from django.utils import timezone

from .errors import classify_exception
from .models import AgentTrace, AgentTraceStep


class _StepHandle:
    """Returned by Tracer.step() — lets the caller attach small,
    non-sensitive metadata while the step is in progress."""

    def __init__(self, step: AgentTraceStep):
        self.metadata = {}
        self._step = step


class Tracer:
    def __init__(self, *, conversation, patient):
        self.conversation = conversation
        self.patient = patient
        self._request_id = uuid.uuid4()
        self._started_at = time.monotonic()
        self._step_index = 0
        self.trace = AgentTrace.objects.create(
            request_id=self._request_id, conversation=conversation, patient=patient, status=AgentTrace.Status.RUNNING
        )

    @property
    def request_id(self) -> uuid.UUID:
        return self._request_id

    @contextmanager
    def step(self, component: str, action: str):
        step_started = time.monotonic()
        self._step_index += 1
        step = AgentTraceStep.objects.create(
            trace=self.trace,
            step_index=self._step_index,
            component=component,
            action=action,
            status=AgentTraceStep.Status.RUNNING,
        )
        handle = _StepHandle(step)

        try:
            yield handle
        except Exception as exc:
            step.status = AgentTraceStep.Status.FAILED
            handle.metadata.setdefault("error_type", classify_exception(exc))
            raise
        else:
            step.status = AgentTraceStep.Status.COMPLETED
        finally:
            step.metadata = handle.metadata
            step.completed_at = timezone.now()
            step.latency_ms = round((time.monotonic() - step_started) * 1000)
            step.save(update_fields=["status", "metadata", "completed_at", "latency_ms"])

    def finish(self, *, status: str, final_agent: str = "", error_type: str = ""):
        self.trace.status = status
        self.trace.final_agent = final_agent
        self.trace.error_type = error_type
        self.trace.completed_at = timezone.now()
        self.trace.total_latency_ms = round((time.monotonic() - self._started_at) * 1000)
        self.trace.save(update_fields=["status", "final_agent", "error_type", "completed_at", "total_latency_ms"])
