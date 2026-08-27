from django.contrib import admin

from .models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("id", "first_name", "last_name", "user", "created_at")
    search_fields = ("first_name", "last_name", "user__username", "user__email")
