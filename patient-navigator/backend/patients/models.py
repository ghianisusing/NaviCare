from django.conf import settings
from django.db import models


class Patient(models.Model):
    """A patient profile, one-to-one with a Django auth User.

    Deliberately minimal for Phase 1: no diagnoses, medications, or other
    clinical data. Extend this model in later phases rather than bolting
    sensitive fields onto it ad hoc.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="patient",
    )
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    date_of_birth = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=32, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip() or self.user.username
