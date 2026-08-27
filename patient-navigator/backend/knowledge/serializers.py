from rest_framework import serializers

from .models import HealthcareDocument


class HealthcareDocumentSerializer(serializers.ModelSerializer):
    chunk_count = serializers.IntegerField(source="chunks.count", read_only=True)

    class Meta:
        model = HealthcareDocument
        fields = (
            "id",
            "title",
            "content",
            "source",
            "source_url",
            "category",
            "chunk_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "chunk_count", "created_at", "updated_at")
