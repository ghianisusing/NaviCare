"""
Curated development seed data for the scheduling domain — departments,
fictional providers, and availability windows.

Providers here are clearly fictional development records (see the name
choices below) and must never be presented as real healthcare
professionals.
"""

from datetime import timedelta

from django.utils import timezone

DEPARTMENTS = [
    dict(name="General Medicine", description="Routine checkups and general health concerns."),
    dict(name="Dermatology", description="Skin, hair, and nail conditions."),
    dict(name="Pediatrics", description="Healthcare for infants, children, and adolescents."),
    dict(name="Cardiology", description="Heart and cardiovascular health."),
    dict(name="Orthopedics", description="Bones, joints, and musculoskeletal conditions."),
]

# (first_name, last_name, title, department_name, bio)
PROVIDERS = [
    ("Maya", "Santos", "MD", "General Medicine", "Fictional development provider — General Medicine."),
    ("Alex", "Rivera", "MD", "Dermatology", "Fictional development provider — Dermatology."),
    ("Jordan", "Lee", "MD", "Pediatrics", "Fictional development provider — Pediatrics."),
    ("Priya", "Nair", "MD", "Cardiology", "Fictional development provider — Cardiology."),
    ("Samuel", "Okafor", "MD", "Orthopedics", "Fictional development provider — Orthopedics."),
    ("Elena", "Petrova", "NP", "General Medicine", "Fictional development provider — General Medicine."),
]


def get_department_data() -> list[dict]:
    return list(DEPARTMENTS)


def get_provider_data() -> list[tuple]:
    return list(PROVIDERS)


def build_availability_windows(provider, *, days_ahead: int = 10, daily_start_hour: int = 9, daily_end_hour: int = 16):
    """Generate simple weekday 9am-4pm availability windows for a
    provider, starting tomorrow, for `days_ahead` calendar days —
    enough for development/demo booking flows without needing a real
    scheduling calendar."""
    now = timezone.now()
    windows = []
    for day_offset in range(1, days_ahead + 1):
        day = (now + timedelta(days=day_offset)).replace(hour=daily_start_hour, minute=0, second=0, microsecond=0)
        if day.weekday() >= 5:  # skip weekends
            continue
        end = day.replace(hour=daily_end_hour)
        windows.append((day, end))
    return windows
