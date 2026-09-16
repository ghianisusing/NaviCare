from django.conf import settings
from django.db import models

from patients.models import Patient


class Conversation(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="conversations")
    title = models.CharField(max_length=255, blank=True, default="New conversation")
    summary = models.TextField(
        blank=True,
        default="",
        help_text="Rolling, non-clinical summary of the conversation used as LLM context. "
        "Never contains diagnoses or medical assumptions — see agents/navigator/prompts.py.",
    )

    # Consecutive failed agent turns (LLM/tool/validation errors — not
    # emergency escalations or normal clarifying questions). Reset to 0
    # on any successful turn. Used by agents/navigator/service.py to
    # trigger an automatic REPEATED_FAILURE escalation once it reaches
    # settings.MAX_AGENT_FAILURES_BEFORE_ESCALATION — see Phase 6.
    consecutive_agent_failures = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title or f"Conversation {self.pk}"


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"
        STAFF = "staff", "Staff"  # a human care coordinator response — see Phase 6

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()

    # Populated only when role=STAFF — identifies which staff member
    # sent a human response during an escalation, so the frontend can
    # clearly label it "Care Support" rather than impersonating the AI
    # assistant (or vice versa). See escalations/services/escalation_service.py.
    sender_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="staff_messages"
    )

    # Populated only for assistant messages. `urgency` mirrors the
    # safety hierarchy (informational/normal, routine, urgent,
    # emergency) so the frontend can style a message appropriately, e.g.
    # an emergency banner — see agents/navigator/service.py for where
    # these are set. `sources` holds the (deterministically retrieved,
    # never LLM-invented) citations for Information Agent answers.
    urgency = models.CharField(max_length=16, blank=True, default="")
    sources = models.JSONField(blank=True, default=list)

    # Populated only for Appointment Agent turns. `appointment_data`
    # holds read-only tool results the frontend renders as selectable
    # cards (slots/appointments/departments/providers — see
    # agents/appointment/service.py:_build_appointment_data).
    # `pending_action` references an AgentAction awaiting explicit
    # patient confirmation via appointments/views.py's confirm/decline
    # endpoints — never executed just because it was proposed.
    appointment_data = models.JSONField(blank=True, null=True, default=None)
    pending_action = models.JSONField(blank=True, null=True, default=None)

    # Populated only for Follow-Up Agent turns — the follow-up/reminder
    # equivalent of appointment_data (see
    # agents/follow_up/service.py:_build_follow_up_data). Pending
    # complete/cancel proposals still use the shared `pending_action`
    # field above (AgentAction is a domain-agnostic record).
    follow_up_data = models.JSONField(blank=True, null=True, default=None)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.role}] {self.content[:40]}"
