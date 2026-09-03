from django.contrib import admin

from .models import FollowUp, Reminder


class ReminderInline(admin.TabularInline):
    model = Reminder
    extra = 0
    readonly_fields = ("scheduled_for", "status", "sent_at", "created_at")


@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display = ("title", "patient", "status", "priority", "due_at")
    list_filter = ("status", "priority")
    search_fields = ("title", "patient__first_name", "patient__last_name")
    inlines = [ReminderInline]


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ("follow_up", "scheduled_for", "status", "sent_at")
    list_filter = ("status",)
