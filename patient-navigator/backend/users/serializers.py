from django.contrib.auth import password_validation
from django.contrib.auth.models import User
from rest_framework import serializers

from patients.models import Patient


class RegisterSerializer(serializers.ModelSerializer):
    """Creates a User + an associated (initially minimal) Patient profile.

    Password strength is enforced through Django's own validators
    (see AUTH_PASSWORD_VALIDATORS in settings) so the rules stay in one
    place rather than being duplicated on the frontend and backend.
    """

    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    first_name = serializers.CharField(write_only=True, max_length=150)
    last_name = serializers.CharField(write_only=True, max_length=150)

    class Meta:
        model = User
        fields = ("id", "username", "email", "password", "first_name", "last_name")
        read_only_fields = ("id",)

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        first_name = validated_data.pop("first_name")
        last_name = validated_data.pop("last_name")
        password = validated_data.pop("password")

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        # Every registered user immediately gets a Patient profile —
        # Phase 1 treats "user" and "patient" as 1:1.
        Patient.objects.create(
            user=user,
            first_name=first_name,
            last_name=last_name,
        )
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email")
        read_only_fields = fields
