from django.contrib import admin

from .models import SafetyRule


@admin.register(SafetyRule)
class SafetyRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "severity", "category", "active", "version", "updated_at")
    list_filter = ("severity", "category", "active")
    search_fields = ("name", "trigger")
