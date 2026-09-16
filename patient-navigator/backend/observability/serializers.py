from rest_framework import serializers

from .models import AgentTrace, AgentTraceStep


class AgentTraceStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentTraceStep
        fields = ("id", "step_index", "component", "action", "status", "metadata", "latency_ms", "started_at", "completed_at")
        read_only_fields = fields


class AgentTraceListSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentTrace
        fields = (
            "id",
            "request_id",
            "conversation",
            "patient",
            "status",
            "final_agent",
            "error_type",
            "started_at",
            "completed_at",
            "total_latency_ms",
        )
        read_only_fields = fields


class AgentTraceDetailSerializer(AgentTraceListSerializer):
    steps = AgentTraceStepSerializer(many=True, read_only=True)

    class Meta(AgentTraceListSerializer.Meta):
        fields = AgentTraceListSerializer.Meta.fields + ("steps",)
