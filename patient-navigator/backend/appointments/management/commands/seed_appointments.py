"""
Seeds development departments, fictional providers, and their
availability windows. Idempotent by name.
"""

from django.core.management.base import BaseCommand

from appointments.models import Availability, Department, Provider
from appointments.seed_data import build_availability_windows, get_department_data, get_provider_data


class Command(BaseCommand):
    help = "Seed departments, fictional providers, and availability windows for development."

    def handle(self, *args, **options):
        department_count = 0
        for dept_data in get_department_data():
            _, created = Department.objects.update_or_create(name=dept_data["name"], defaults=dept_data)
            department_count += created

        provider_count = 0
        availability_count = 0
        for first_name, last_name, title, department_name, bio in get_provider_data():
            department = Department.objects.get(name=department_name)
            provider, created = Provider.objects.update_or_create(
                first_name=first_name,
                last_name=last_name,
                defaults={"department": department, "title": title, "bio": bio, "active": True},
            )
            provider_count += created

            # Only (re-)generate availability if this provider has none
            # yet, so re-running the command doesn't keep stacking
            # windows on top of existing ones.
            if not provider.availability_windows.exists():
                Availability.objects.bulk_create(
                    [
                        Availability(provider=provider, start_time=start, end_time=end)
                        for start, end in build_availability_windows(provider)
                    ]
                )
                availability_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Appointment seed data ready: {department_count} departments created, "
                f"{provider_count} providers created, {availability_count} providers given fresh availability."
            )
        )
