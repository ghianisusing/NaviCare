from django.apps import AppConfig


class AppointmentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "appointments"

    def ready(self):
        # Registers every appointment tool with the central tool
        # registry (tools/registry.py) as a side effect of import. Done
        # here, once, at app startup, rather than scattered import-time
        # side effects elsewhere.
        import tools.appointment_tools  # noqa: F401
