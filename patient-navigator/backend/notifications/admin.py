from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "patient", "type", "read", "created_at")
    list_filter = ("type", "read")
    search_fields = ("title", "patient__first_name", "patient__last_name")
