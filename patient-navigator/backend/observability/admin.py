from django.contrib import admin

from .models import AgentTrace, AgentTraceStep


class AgentTraceStepInline(admin.TabularInline):
    model = AgentTraceStep
    extra = 0
    readonly_fields = ("step_index", "component", "action", "status", "metadata", "latency_ms")
    can_delete = False


@admin.register(AgentTrace)
class AgentTraceAdmin(admin.ModelAdmin):
    list_display = ("request_id", "status", "final_agent", "error_type", "total_latency_ms", "started_at")
    list_filter = ("status", "final_agent", "error_type")
    inlines = [AgentTraceStepInline]
