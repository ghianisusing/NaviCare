from rest_framework import serializers

from .models import AgentAction, Appointment, Availability, Department, Provider


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ("id", "name", "description")
        read_only_fields = fields


class ProviderSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    name = serializers.CharField(source="display_name", read_only=True)

    class Meta:
        model = Provider
        fields = ("id", "name", "department", "department_name", "title", "bio")
        read_only_fields = fields


class AppointmentSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="provider.display_name", read_only=True)
    department_name = serializers.CharField(source="provider.department.name", read_only=True)

    class Meta:
        model = Appointment
        fields = (
            "id",
            "provider",
            "provider_name",
            "department_name",
            "start_time",
            "end_time",
            "status",
            "reason",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "provider_name", "department_name", "status", "created_at", "updated_at")


class AppointmentCreateSerializer(serializers.Serializer):
    """Direct-booking input for the REST API (as opposed to the
    agent/chat path) — validated the same way tool arguments are,
    then handed to the same appointment_service.book_appointment()."""

    provider = serializers.IntegerField()
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class RescheduleSerializer(serializers.Serializer):
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()


class AvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Availability
        fields = ("id", "provider", "start_time", "end_time", "is_available")
        read_only_fields = fields


class AgentActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentAction
        fields = ("id", "tool_name", "status", "result_summary", "created_at")
        read_only_fields = fields
