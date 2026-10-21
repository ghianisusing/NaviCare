import datetime as dt
from types import SimpleNamespace

from django.test import SimpleTestCase

from core.datetime_format import format_patient_datetime

UTC = dt.timezone.utc


def _patient(tz):
    return SimpleNamespace(timezone=tz)


class FormatPatientDatetimeTests(SimpleTestCase):
    def test_renders_in_patient_timezone_without_padding(self):
        value = dt.datetime(2026, 3, 3, 14, 5, tzinfo=UTC)  # 9:05 AM in New York (EST)
        self.assertEqual(
            format_patient_datetime(value, _patient("America/New_York"), with_year=True),
            "Tuesday, March 3, 2026 · 9:05 AM EST",
        )

    def test_local_date_can_differ_from_utc_date(self):
        value = dt.datetime(2026, 7, 1, 2, 30, tzinfo=UTC)  # evening of June 30 in Los Angeles
        self.assertEqual(
            format_patient_datetime(value, _patient("America/Los_Angeles"), joiner=" at "),
            "Tuesday, June 30 at 7:30 PM PDT",
        )

    def test_noon_and_midnight(self):
        self.assertTrue(
            format_patient_datetime(dt.datetime(2026, 1, 5, 12, 0, tzinfo=UTC), _patient("UTC")).endswith("12:00 PM UTC")
        )
        self.assertTrue(
            format_patient_datetime(dt.datetime(2026, 1, 5, 0, 0, tzinfo=UTC), _patient("UTC")).endswith("12:00 AM UTC")
        )

    def test_unknown_timezone_falls_back_to_utc(self):
        value = dt.datetime(2026, 1, 5, 8, 0, tzinfo=UTC)
        self.assertTrue(format_patient_datetime(value, _patient("Not/AZone")).endswith("8:00 AM UTC"))
