"""
Human escalation — the record of a conversation being handed to a human
care coordinator.

Escalation is a *designed capability*, not a failure state: see
agents/escalation/ and the Phase 6 principle that the system should
recognize when it should hand off rather than keep guessing. `priority`
is deliberately a plain normal/high operational field — never a
clinical severity value. Emergency handling stays entirely inside the
deterministic safety layer (safety/) and never creates an Escalation
row; it is handled immediately and does not wait in a support queue.
"""

from django.conf import settings
from django.db import models

from conversations.models import Conversation
from patients.models import Patient


class Escalation(models.Model):
    class Reason(models.TextChoices):
        PATIENT_REQUEST = "patient_request", "Patient Request"
        OUT_OF_SCOPE = "out_of_scope", "Out of Scope"
        REPEATED_FAILURE = "repeated_failure", "Repeated Failure"
        SAFETY_REVIEW = "safety_review", "Safety Review"
        ADMINISTRATIVE_ISSUE = "administrative_issue", "Administrative Issue"
        HUMAN_ASSISTANCE_REQUIRED = "human_assistance_required", "Human Assistance Required"

    class Priority(models.TextChoices):
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ASSIGNED = "assigned", "Assigned"
        IN_PROGRESS = "in_progress", "In Progress"
        RESOLVED = "resolved", "Resolved"
        CANCELLED = "cancelled", "Cancelled"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="escalations")
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="escalations")

    reason = models.CharField(max_length=32, choices=Reason.choices)
    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)

    # A structured, deterministically-built internal summary for staff
    # (see escalation_service.build_internal_summary) — never a
    # diagnosis, never the raw conversation dump. Shape documented in
    # agents/escalation/schemas.py.
    summary = models.JSONField(default=dict, blank=True)

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_escalations"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-priority", "created_at"]
        indexes = [models.Index(fields=["status", "priority"])]

    def __str__(self):
        return f"Escalation #{self.id} [{self.status}] for {self.patient} ({self.reason})"


class EscalationEvent(models.Model):
    """Audit trail entry for a human-facing action on an escalation —
    created / assigned / resolved / staff response sent. `actor` is
    null for system-initiated events (e.g. an automatic
    REPEATED_FAILURE escalation)."""

    class Action(models.TextChoices):
        CREATED = "created", "Created"
        ASSIGNED = "assigned", "Assigned"
        STATUS_CHANGED = "status_changed", "Status Changed"
        STAFF_RESPONSE_SENT = "staff_response_sent", "Staff Response Sent"
        RESOLVED = "resolved", "Resolved"
        CANCELLED = "cancelled", "Cancelled"

    escalation = models.ForeignKey(Escalation, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="escalation_events"
    )
    action = models.CharField(max_length=32, choices=Action.choices)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        actor_label = self.actor.username if self.actor else "system"
        return f"{self.action} by {actor_label} on escalation #{self.escalation_id}"
