from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = (
            "id",
            "type",
            "title",
            "message",
            "related_follow_up",
            "related_appointment",
            "read",
            "created_at",
            "read_at",
        )
        read_only_fields = fields
