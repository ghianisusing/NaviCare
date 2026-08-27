from rest_framework import serializers

from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ("id", "conversation", "role", "content", "created_at")
        read_only_fields = ("id", "conversation", "role", "created_at")


class MessageCreateSerializer(serializers.ModelSerializer):
    """Only `content` is accepted from the client — role is always "user"
    and is set server-side in the view, never trusted from the request."""

    class Meta:
        model = Message
        fields = ("content",)

    def validate_content(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Message content cannot be empty.")
        if len(value) > 8000:
            raise serializers.ValidationError("Message is too long.")
        return value


class ConversationListSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ("id", "title", "created_at", "updated_at", "last_message")
        read_only_fields = fields

    def get_last_message(self, obj):
        last = obj.messages.order_by("-created_at").first()
        return MessageSerializer(last).data if last else None


class ConversationDetailSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = ("id", "title", "created_at", "updated_at", "messages")
        read_only_fields = fields


class ConversationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ("id", "title", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")
