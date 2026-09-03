"""
Stand-in for a Celery Beat periodic task: sends any due reminders and
marks overdue follow-ups as expired. Run this on a schedule (cron,
Heroku Scheduler, etc.) — see notifications/tasks.py's docstring for
why this is a management command rather than a Celery task here.
"""

from django.core.management.base import BaseCommand

from notifications.tasks import run_maintenance_cycle


class Command(BaseCommand):
    help = "Process due reminders (send notifications) and expire overdue follow-ups."

    def handle(self, *args, **options):
        result = run_maintenance_cycle()
        self.stdout.write(
            self.style.SUCCESS(
                f"Reminders sent: {result['reminders_sent']}, follow-ups expired: {result['follow_ups_expired']}"
            )
        )
