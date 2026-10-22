"""
Creates local test accounts, one per role, for trying the app by hand.

    python manage.py seed_demo_users

Accounts (all share the password below):

    demo_patient       patient: chat, appointments, follow-ups
    demo_coordinator   care coordinator (is_staff): Care Support queue
    demo_admin         system admin (is_superuser): Agent Monitoring, /admin/

These passwords are public — they're in this file. The command refuses
to run unless DEBUG=True, so it can't create them on a real deployment.
Idempotent: rerunning resets the accounts' roles and password.
"""

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from patients.models import Patient

DEMO_PASSWORD = "navicare-demo-2026"

DEMO_USERS = [
    dict(username="demo_patient", first_name="Dana", last_name="Patient", is_staff=False, is_superuser=False),
    dict(username="demo_coordinator", first_name="Casey", last_name="Coordinator", is_staff=True, is_superuser=False),
    dict(username="demo_admin", first_name="Alex", last_name="Admin", is_staff=True, is_superuser=True),
]


class Command(BaseCommand):
    help = "Create local test accounts for each role (DEBUG only)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo_users only runs with DEBUG=True; its passwords are public.")

        with transaction.atomic():
            for spec in DEMO_USERS:
                user, created = User.objects.get_or_create(
                    username=spec["username"],
                    defaults={"email": f"{spec['username']}@example.test"},
                )
                user.is_staff = spec["is_staff"]
                user.is_superuser = spec["is_superuser"]
                user.is_active = True
                user.set_password(DEMO_PASSWORD)
                user.save()
                # Registration always creates a Patient profile, so match it.
                Patient.objects.update_or_create(
                    user=user,
                    defaults={"first_name": spec["first_name"], "last_name": spec["last_name"]},
                )
                self.stdout.write(f"{'Created' if created else 'Updated'} {spec['username']}")

        self.stdout.write(self.style.SUCCESS("Demo users ready. Credentials are in users/management/commands/seed_demo_users.py"))
