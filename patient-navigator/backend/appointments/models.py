"""
Healthcare scheduling domain models.

Providers/departments/availability here are fictional development
records — see appointments/seed_data.py — never presented as real
healthcare professionals or a real scheduling system.
"""

from django.db import models
from django.db.models import Q

from patients.models import Patient


class Department(models.Model):
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Provider(models.Model):
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="providers")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    title = models.CharField(max_length=100, blank=True, help_text="e.g. MD, Nurse Practitioner")
    bio = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"Dr. {self.first_name} {self.last_name} ({self.department.name})"

    @property
    def display_name(self) -> str:
        # Matches the "Dr. Jane Smith" style from the spec; non-physician
        # titles (e.g. Nurse Practitioner) are shown as a suffix instead.
        if self.title and self.title.upper() in ("NP", "PA"):
            return f"{self.first_name} {self.last_name}, {self.title}"
        return f"Dr. {self.first_name} {self.last_name}"


class Availability(models.Model):
    """A window during which a provider can be booked. Concrete bookable
    slots are derived from these windows at query time (see
    appointments/services/appointment_service.py) rather than
    pre-materialized, keeping seed data simple."""

    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="availability_windows")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    is_available = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_time"]
        constraints = [
            models.CheckConstraint(condition=Q(end_time__gt=models.F("start_time")), name="availability_end_after_start")
        ]

    def __str__(self):
        return f"{self.provider} — {self.start_time:%Y-%m-%d %H:%M} to {self.end_time:%H:%M}"


class Appointment(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"
        NO_SHOW = "no_show", "No Show"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="appointments")
    provider = models.ForeignKey(Provider, on_delete=models.PROTECT, related_name="appointments")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SCHEDULED)
    reason = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_time"]
        constraints = [
            models.CheckConstraint(condition=Q(end_time__gt=models.F("start_time")), name="appointment_end_after_start"),
            # Enforced at the database level, not just in application code:
            # only one *scheduled* appointment can exist for a given
            # provider/start_time. This is the backstop against a race
            # between two concurrent booking requests for the same slot —
            # see appointment_service.book_appointment for the
            # transaction + row lock that normally prevents the race
            # before it ever reaches this constraint.
            models.UniqueConstraint(
                fields=["provider", "start_time"],
                condition=Q(status="scheduled"),
                name="unique_scheduled_provider_slot",
            ),
        ]
        indexes = [
            models.Index(fields=["patient", "status"]),
            models.Index(fields=["provider", "start_time"]),
        ]

    def __str__(self):
        return f"{self.patient} with {self.provider} at {self.start_time:%Y-%m-%d %H:%M} [{self.status}]"


class AgentAction(models.Model):
    """Audit log of tool calls the agent layer attempted, plus the
    pending-confirmation record for mutating actions (see
    appointments/services/appointment_service.py and
    agents/appointment/service.py).

    Arguments are stored as a JSON dict but callers are expected to keep
    them to identifiers (slot/appointment/provider ids, dates) rather
    than free text — see the docstring on `arguments` below.
    """

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        VALIDATED = "validated", "Validated"  # passed validation, awaiting patient confirmation
        EXECUTED = "executed", "Executed"
        REJECTED = "rejected", "Rejected"  # failed validation/authorization
        DECLINED = "declined", "Declined"  # patient explicitly declined
        FAILED = "failed", "Failed"  # passed validation but execution failed (e.g. race lost)

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="agent_actions")
    conversation = models.ForeignKey(
        "conversations.Conversation", on_delete=models.CASCADE, related_name="agent_actions"
    )
    agent = models.CharField(max_length=32, default="appointment")
    tool_name = models.CharField(max_length=64)

    # Identifiers/dates only — never store free-text patient content here.
    arguments = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.REQUESTED)
    result_summary = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tool_name} [{self.status}] for {self.patient}"
