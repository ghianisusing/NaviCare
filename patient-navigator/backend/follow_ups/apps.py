from django.apps import AppConfig


class FollowUpsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "follow_ups"

    def ready(self):
        # Registers every follow-up/reminder tool with the central tool
        # registry (tools/registry.py) as a side effect of import.
        import tools.follow_up_tools  # noqa: F401
