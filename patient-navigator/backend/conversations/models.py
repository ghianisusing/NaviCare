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

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()

    # Populated only for assistant messages. `urgency` mirrors the
    # safety hierarchy (informational/normal, routine, urgent,
    # emergency) so the frontend can style a message appropriately, e.g.
    # an emergency banner — see agents/navigator/service.py for where
    # these are set. `sources` holds the (deterministically retrieved,
    # never LLM-invented) citations for Information Agent answers.
    urgency = models.CharField(max_length=16, blank=True, default="")
    sources = models.JSONField(blank=True, default=list)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.role}] {self.content[:40]}"
