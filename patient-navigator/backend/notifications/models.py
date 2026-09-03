"""
In-app notifications — the first channel of the notification
abstraction (see notifications/services.py for the `NotificationService`
interface future channels like email/SMS/push would implement).
"""

from django.db import models

from appointments.models import Appointment
from follow_ups.models import FollowUp
from patients.models import Patient


class Notification(models.Model):
    class Type(models.TextChoices):
        APPOINTMENT_REMINDER = "appointment_reminder", "Appointment Reminder"
        FOLLOW_UP_REMINDER = "follow_up_reminder", "Follow-Up Reminder"
        SYSTEM = "system", "System"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=32, choices=Type.choices)
    title = models.CharField(max_length=200)
    # Kept short and non-clinical by convention — see
    # notifications/services.py's message templates. Never includes raw
    # patient conversation content.
    message = models.CharField(max_length=500)

    related_follow_up = models.ForeignKey(
        FollowUp, on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications"
    )
    related_appointment = models.ForeignKey(
        Appointment, on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications"
    )

    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["patient", "read"])]

    def __str__(self):
        return f"{self.title} for {self.patient} [{'read' if self.read else 'unread'}]"
