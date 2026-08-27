"""
Seeds (or updates) the default safety rule set.

Idempotent: running this repeatedly updates existing rules by name
rather than creating duplicates, so it's safe to run on every deploy.
"""

from django.core.management.base import BaseCommand

from safety.models import SafetyRule
from safety.rules import get_default_rules


class Command(BaseCommand):
    help = "Seed the database with the default set of safety rules."

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for rule_data in get_default_rules():
            _, created = SafetyRule.objects.update_or_create(
                name=rule_data["name"],
                defaults={
                    "category": rule_data["category"],
                    "trigger": rule_data["trigger"],
                    "severity": rule_data["severity"],
                    "response": rule_data["response"],
                    "active": True,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(f"Safety rules seeded: {created_count} created, {updated_count} updated."))
