from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers


User = get_user_model()


class RegistrationSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={"input_type": "password"},
    )

    def validate_email(self, value):
        email = value.strip().casefold()
        email_field = User.get_email_field_name()
        if User._default_manager.filter(**{f"{email_field}__iexact": email}).exists():
            raise serializers.ValidationError(
                "An account with this email address already exists."
            )
        return email

    def validate(self, attrs):
        full_name = " ".join(attrs["full_name"].split())
        if not full_name:
            raise serializers.ValidationError(
                {"full_name": "Enter your name."}
            )
        attrs["full_name"] = full_name

        user = User()
        setattr(user, User.get_email_field_name(), attrs["email"])
        if hasattr(user, "first_name"):
            name_parts = full_name.split(maxsplit=1)
            user.first_name = name_parts[0]
            if len(name_parts) == 2 and hasattr(user, "last_name"):
                user.last_name = name_parts[1]
        try:
            password_validation.validate_password(attrs["password"], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                {"password": list(exc.messages)}
            ) from exc
        return attrs

    def create(self, validated_data):
        full_name = validated_data["full_name"]
        name_parts = full_name.split(maxsplit=1)
        user = User(**{User.USERNAME_FIELD: validated_data["email"]})
        setattr(user, User.get_email_field_name(), validated_data["email"])
        if hasattr(user, "first_name"):
            user.first_name = name_parts[0]
        if hasattr(user, "last_name") and len(name_parts) == 2:
            user.last_name = name_parts[1]
        user.set_password(validated_data["password"])
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={"input_type": "password"},
    )

    def validate_email(self, value):
        return value.strip().casefold()


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().casefold()


class PasswordResetConfirmSerializer(serializers.Serializer):
    new_password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={"input_type": "password"},
    )
    new_password_confirm = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={"input_type": "password"},
    )

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "The passwords do not match."}
            )
        try:
            password_validation.validate_password(
                attrs["new_password"], user=self.context["user"]
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                {"new_password": list(exc.messages)}
            ) from exc
        return attrs
