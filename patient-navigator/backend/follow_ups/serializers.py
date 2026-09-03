from rest_framework import serializers

from .models import FollowUp, Reminder


class FollowUpSerializer(serializers.ModelSerializer):
    appointment_provider_name = serializers.CharField(source="appointment.provider.display_name", read_only=True, default=None)

    class Meta:
        model = FollowUp
        fields = (
            "id",
            "title",
            "description",
            "due_at",
            "status",
            "priority",
            "appointment",
            "appointment_provider_name",
            "created_at",
            "updated_at",
            "completed_at",
        )
        read_only_fields = ("id", "status", "created_at", "updated_at", "completed_at")


class FollowUpCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    due_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    priority = serializers.ChoiceField(choices=FollowUp.Priority.choices, required=False, default=FollowUp.Priority.NORMAL)
    appointment = serializers.IntegerField(required=False, allow_null=True, default=None)


class ReminderSerializer(serializers.ModelSerializer):
    follow_up_title = serializers.CharField(source="follow_up.title", read_only=True)

    class Meta:
        model = Reminder
        fields = ("id", "follow_up", "follow_up_title", "scheduled_for", "status", "sent_at", "created_at")
        read_only_fields = ("id", "follow_up_title", "status", "sent_at", "created_at")


class ReminderCreateSerializer(serializers.Serializer):
    follow_up = serializers.IntegerField()
    scheduled_for = serializers.DateTimeField()


class AppointmentReminderSerializer(serializers.Serializer):
    """Input for the one-shot 'remind me before this appointment' action
    offered right after booking."""

    appointment = serializers.IntegerField()
    hours_before = serializers.IntegerField(required=False, default=24, min_value=1, max_value=24 * 14)
