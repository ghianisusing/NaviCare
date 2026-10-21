from django.conf import settings
from django.db import migrations, models

OPEN_STATUSES = ["pending", "assigned", "in_progress"]


def cancel_duplicate_open_escalations(apps, schema_editor):
    """Existing data may already hold several open escalations for one
    conversation (the race this constraint closes). Keep the oldest open
    one per conversation and cancel the rest so the constraint can be
    added."""
    Escalation = apps.get_model("escalations", "Escalation")
    EscalationEvent = apps.get_model("escalations", "EscalationEvent")

    seen = set()
    for escalation in Escalation.objects.filter(status__in=OPEN_STATUSES).order_by("conversation_id", "created_at", "id"):
        if escalation.conversation_id not in seen:
            seen.add(escalation.conversation_id)
            continue
        escalation.status = "cancelled"
        escalation.save(update_fields=["status"])
        EscalationEvent.objects.create(
            escalation=escalation,
            actor=None,
            action="cancelled",
            metadata={"reason": "duplicate_open_escalation_migration"},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("conversations", "0006_conversation_consecutive_agent_failures_and_more"),
        ("escalations", "0001_initial"),
        ("patients", "0002_patient_timezone"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(cancel_duplicate_open_escalations, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="escalation",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status__in", OPEN_STATUSES)),
                fields=("conversation",),
                name="unique_open_escalation_per_conversation",
            ),
        ),
    ]
