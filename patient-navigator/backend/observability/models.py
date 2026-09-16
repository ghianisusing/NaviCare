"""
Agent execution traces — structured, developer/admin-facing
observability for a single patient turn.

Deliberately records *structured events* (which component ran, which
tool, what the safety decision was, latency, error type) rather than
hidden reasoning or full prompts — see the Phase 6 principle that
observability is not the same as exposing chain-of-thought. Nothing
here stores a complete patient message or a full LLM prompt/response;
`metadata` on a step is a small, curated dict (tool name, retrieval
count, similarity score, rule name — never raw content).
"""

from django.db import models

from conversations.models import Conversation
from patients.models import Patient


class AgentTrace(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        ESCALATED = "escalated", "Escalated"

    class ErrorType(models.TextChoices):
        LLM_ERROR = "llm_error", "LLM Error"
        TOOL_ERROR = "tool_error", "Tool Error"
        DATABASE_ERROR = "database_error", "Database Error"
        VALIDATION_ERROR = "validation_error", "Validation Error"
        AUTHORIZATION_ERROR = "authorization_error", "Authorization Error"
        RETRIEVAL_ERROR = "retrieval_error", "Retrieval Error"
        SAFETY_ERROR = "safety_error", "Safety Error"
        TIMEOUT = "timeout", "Timeout"
        UNKNOWN_ERROR = "unknown_error", "Unknown Error"

    # Correlates every step/log line for one patient turn — also usable
    # as an external correlation id (e.g. in logs) since it's a UUID,
    # not the auto-increment primary key.
    request_id = models.UUIDField(unique=True, db_index=True)

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="agent_traces")
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="agent_traces")

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RUNNING)
    final_agent = models.CharField(max_length=32, blank=True, default="")
    error_type = models.CharField(max_length=32, choices=ErrorType.choices, blank=True, default="")

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    total_latency_ms = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["patient", "started_at"]), models.Index(fields=["status"])]

    def __str__(self):
        return f"Trace {self.request_id} [{self.status}]"


class AgentTraceStep(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    trace = models.ForeignKey(AgentTrace, on_delete=models.CASCADE, related_name="steps")
    step_index = models.PositiveIntegerField()
    component = models.CharField(max_length=64)  # e.g. "navigator", "safety", "information", "tool"
    action = models.CharField(max_length=64)  # e.g. "classify_intent", "evaluate_rules", "find_available_slots"
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RUNNING)

    # Small, curated, non-sensitive detail only — see module docstring.
    metadata = models.JSONField(default=dict, blank=True)

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["trace_id", "step_index"]
        constraints = [
            models.UniqueConstraint(fields=["trace", "step_index"], name="unique_step_index_per_trace")
        ]

    def __str__(self):
        return f"{self.component}.{self.action} [{self.status}]"
