"""
Patient-facing date/time formatting.

Datetimes are stored in UTC; anything shown to a patient is rendered in
their `Patient.timezone`. The formatting avoids the glibc-only `%-d` /
`%-I` strftime flags, which raise ValueError on Windows.
"""

from __future__ import annotations

import zoneinfo
from datetime import datetime

from django.utils import timezone as dj_timezone


def patient_tzinfo(patient) -> zoneinfo.ZoneInfo:
    name = getattr(patient, "timezone", "") or "UTC"
    try:
        return zoneinfo.ZoneInfo(name)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        return zoneinfo.ZoneInfo("UTC")


def format_patient_datetime(value: datetime, patient, *, with_year: bool = False, joiner: str = " · ") -> str:
    """e.g. "Tuesday, March 3, 2026 · 9:05 AM EST".

    Naive datetimes are assumed to be in the server's default timezone
    (UTC), matching how Django stores them.
    """
    if dj_timezone.is_naive(value):
        value = dj_timezone.make_aware(value, dj_timezone.get_default_timezone())
    local = value.astimezone(patient_tzinfo(patient))

    hour = local.hour % 12 or 12
    date_part = f"{local:%A, %B} {local.day}"
    if with_year:
        date_part += f", {local.year}"
    return f"{date_part}{joiner}{hour}:{local:%M} {'AM' if local.hour < 12 else 'PM'} {local.tzname()}"
