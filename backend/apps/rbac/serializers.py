from rest_framework import serializers

from apps.rbac.models import Permission, Role, RolePermission


class RoleCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=80)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True)
    permission_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
    )

    def validate_name(self, value):
        return " ".join(value.split())

    def validate_permission_ids(self, values):
        permissions = Permission.objects.filter(pk__in=set(values), is_active=True)
        found = {permission.pk for permission in permissions}
        if found != set(values):
            raise serializers.ValidationError(
                "One or more selected permissions are unavailable."
            )
        return list(permissions)


class RoleUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=80, required=False)
    description = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
    )
    is_active = serializers.BooleanField(required=False)
    permission_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
    )

    def validate_name(self, value):
        return " ".join(value.split())

    def validate_permission_ids(self, values):
        permissions = Permission.objects.filter(pk__in=set(values), is_active=True)
        found = {permission.pk for permission in permissions}
        if found != set(values):
            raise serializers.ValidationError(
                "One or more selected permissions are unavailable."
            )
        return list(permissions)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "Provide at least one role field to update."
            )
        if self.context["role"].is_system and (
            "name" in attrs or "permission_ids" in attrs or "is_active" in attrs
        ):
            raise serializers.ValidationError(
                "System roles cannot be renamed, deactivated, or have permissions changed."
            )
        return attrs


def serialize_role(role):
    return {
        "id": str(role.pk),
        "name": role.name,
        "description": role.description,
        "is_system": role.is_system,
        "is_active": role.is_active,
        "permissions": [
            {
                "id": str(item.permission_id),
                "codename": item.permission.codename,
                "name": item.permission.name,
                "module": item.permission.module,
            }
            for item in role.role_permissions.select_related("permission").order_by(
                "permission__module", "permission__codename"
            )
        ],
    }


def replace_role_permissions(role, organisation, permissions):
    RolePermission.objects.for_organisation(organisation).filter(role=role).delete()
    RolePermission.objects.bulk_create(
        [
            RolePermission(
                organisation=organisation,
                role=role,
                permission=permission,
            )
            for permission in permissions
        ]
    )
