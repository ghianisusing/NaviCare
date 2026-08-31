from django.contrib import admin

from .models import AgentAction, Appointment, Availability, Department, Provider


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ("display_name", "department", "active")
    list_filter = ("department", "active")
    search_fields = ("first_name", "last_name")


@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = ("provider", "start_time", "end_time", "is_available")
    list_filter = ("is_available",)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("patient", "provider", "start_time", "status")
    list_filter = ("status",)
    search_fields = ("patient__first_name", "patient__last_name")


@admin.register(AgentAction)
class AgentActionAdmin(admin.ModelAdmin):
    list_display = ("tool_name", "status", "patient", "created_at")
    list_filter = ("status", "tool_name")
    readonly_fields = ("arguments", "created_at", "updated_at")
