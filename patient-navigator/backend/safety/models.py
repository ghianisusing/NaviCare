"""
Deterministic, versioned safety rules.

These exist specifically so that emergency/urgency detection does not
depend solely on an LLM's judgment call. Rules are plain regex triggers
with a fixed severity — evaluating them is pure pattern matching, no
model inference involved. See safety/validator.py for how they're
combined into a final decision, and safety/rules.py for the seeded
defaults.

Only staff/admin users can create, edit, or deactivate rules (see
safety/views.py) — patients never have write access to this table.
"""

from django.db import models


class SafetyRule(models.Model):
    class Severity(models.TextChoices):
        EMERGENCY = "emergency", "Emergency"
        URGENT = "urgent", "Urgent"
        ROUTINE = "routine", "Routine"
        INFORMATIONAL = "informational", "Informational"

    class Category(models.TextChoices):
        CARDIAC_RESPIRATORY = "cardiac_respiratory", "Cardiac / Respiratory"
        NEUROLOGICAL = "neurological", "Neurological"
        BLEEDING_TRAUMA = "bleeding_trauma", "Bleeding / Trauma"
        MENTAL_HEALTH_CRISIS = "mental_health_crisis", "Mental Health Crisis"
        ALLERGIC_REACTION = "allergic_reaction", "Allergic Reaction"
        GENERAL = "general", "General"

    name = models.CharField(max_length=200, unique=True)
    category = models.CharField(max_length=32, choices=Category.choices, default=Category.GENERAL)

    # A Python regex (case-insensitive at evaluation time). Kept as plain
    # text rather than a compiled artifact so rules can be edited/added
    # without a code deploy.
    trigger = models.TextField(help_text="Regex pattern matched against the raw patient message.")

    severity = models.CharField(max_length=16, choices=Severity.choices)

    # Fixed, non-LLM-generated text shown to the patient when this rule
    # fires with the highest severity in a given evaluation.
    response = models.TextField(
        help_text="Fixed response shown to the patient when this rule is the deciding match."
    )

    active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-severity", "name"]

    def __str__(self):
        return f"[{self.severity}] {self.name} (v{self.version})"
