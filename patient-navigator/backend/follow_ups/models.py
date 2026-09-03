"""
Navigation follow-up tasks and their reminders.

Deliberately administrative/navigational in scope — see the Phase 5
boundary: a FollowUp tracks things like "contact your clinic" or
"remember your appointment," never a clinical instruction, medication
schedule, or treatment plan. `priority` is intentionally a simple
normal/high scale, not a clinical severity/triage field (that lives in
the Triage Agent / safety layer instead).
"""

from django.db import models

from appointments.models import Appointment
from conversations.models import Conversation
from patients.models import Patient


class FollowUp(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    class Priority(models.TextChoices):
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="follow_ups")
    conversation = models.ForeignKey(
        Conversation, on_delete=models.SET_NULL, null=True, blank=True, related_name="follow_ups"
    )
    appointment = models.ForeignKey(
        Appointment, on_delete=models.SET_NULL, null=True, blank=True, related_name="follow_ups"
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.NORMAL)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["due_at", "-created_at"]
        indexes = [models.Index(fields=["patient", "status"])]

    def __str__(self):
        return f"{self.title} [{self.status}] for {self.patient}"


class Reminder(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        SENT = "sent", "Sent"
        CANCELLED = "cancelled", "Cancelled"
        FAILED = "failed", "Failed"

    follow_up = models.ForeignKey(FollowUp, on_delete=models.CASCADE, related_name="reminders")
    scheduled_for = models.DateTimeField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SCHEDULED)
    sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scheduled_for"]
        indexes = [models.Index(fields=["status", "scheduled_for"])]

    def __str__(self):
        return f"Reminder for {self.follow_up.title} at {self.scheduled_for:%Y-%m-%d %H:%M} [{self.status}]"

    @property
    def patient(self) -> Patient:
        return self.follow_up.patient
