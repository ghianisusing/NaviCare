from rest_framework import serializers

from .models import Escalation, EscalationEvent


class EscalationEventSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True, default=None)

    class Meta:
        model = EscalationEvent
        fields = ("id", "action", "actor_username", "metadata", "created_at")
        read_only_fields = fields


class EscalationListSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    assigned_to_username = serializers.CharField(source="assigned_to.username", read_only=True, default=None)

    class Meta:
        model = Escalation
        fields = (
            "id",
            "patient_name",
            "conversation",
            "reason",
            "priority",
            "status",
            "assigned_to_username",
            "created_at",
            "updated_at",
            "resolved_at",
        )
        read_only_fields = fields

    def get_patient_name(self, obj):
        return f"{obj.patient.first_name} {obj.patient.last_name}".strip()


class EscalationDetailSerializer(EscalationListSerializer):
    events = EscalationEventSerializer(many=True, read_only=True)

    class Meta(EscalationListSerializer.Meta):
        fields = EscalationListSerializer.Meta.fields + ("summary", "events")


class StaffResponseSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=4000)
