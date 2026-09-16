from django.contrib import admin

from .models import Escalation, EscalationEvent


class EscalationEventInline(admin.TabularInline):
    model = EscalationEvent
    extra = 0
    readonly_fields = ("action", "actor", "metadata", "created_at")
    can_delete = False


@admin.register(Escalation)
class EscalationAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "reason", "priority", "status", "assigned_to", "created_at")
    list_filter = ("status", "reason", "priority")
    search_fields = ("patient__first_name", "patient__last_name")
    inlines = [EscalationEventInline]
