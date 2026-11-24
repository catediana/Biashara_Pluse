from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organisations.models import Membership
from apps.rbac.models import Permission, Role
from apps.rbac.serializers import (
    RoleCreateSerializer,
    RoleUpdateSerializer,
    replace_role_permissions,
    serialize_role,
)
from core.permissions import (
    HasAnyOrganisationPermission,
    HasOrganisationPermission,
)


class PermissionListView(APIView):
    permission_classes = [IsAuthenticated, HasOrganisationPermission]
    required_permission = "rbac.manage"

    def get(self, request):
        permissions = Permission.objects.filter(is_active=True)
        return Response(
            {
                "results": [
                    {
                        "id": str(permission.pk),
                        "codename": permission.codename,
                        "name": permission.name,
                        "module": permission.module,
                    }
                    for permission in permissions
                ]
            }
        )


class RoleListCreateView(APIView):
    permission_classes = [IsAuthenticated, HasOrganisationPermission]
    required_permission = "rbac.manage"
    required_permissions = ("staff.manage", "rbac.manage")

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsAuthenticated(), HasAnyOrganisationPermission()]
        return [IsAuthenticated(), HasOrganisationPermission()]

    def get(self, request):
        roles = Role.objects.for_organisation(
            request.active_organisation
        ).order_by("name")
        return Response({"results": [serialize_role(role) for role in roles]})

    @transaction.atomic
    def post(self, request):
        organisation = request.active_organisation
        serializer = RoleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        if Role.objects.for_organisation(organisation).filter(
            name__iexact=values["name"]
        ).exists():
            return Response(
                {"name": ["A role with this name already exists."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        role = Role.objects.create(
            organisation=organisation,
            name=values["name"],
            description=values.get("description", ""),
        )
        replace_role_permissions(
            role,
            organisation,
            values.get("permission_ids", []),
        )
        return Response(serialize_role(role), status=status.HTTP_201_CREATED)


class RoleDetailView(APIView):
    permission_classes = [IsAuthenticated, HasOrganisationPermission]
    required_permission = "rbac.manage"

    @transaction.atomic
    def patch(self, request, role_id):
        organisation = request.active_organisation
        role = (
            Role.objects.for_organisation(organisation)
            .filter(pk=role_id)
            .first()
        )
        if role is None:
            return Response(
                {"detail": "Role not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = RoleUpdateSerializer(
            data=request.data,
            context={"role": role},
        )
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        if values.get("is_active") is False and Membership.objects.for_organisation(
            organisation
        ).filter(role=role, status=Membership.Status.ACTIVE).exists():
            return Response(
                {
                    "is_active": [
                        "A role assigned to active staff cannot be deactivated."
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if "name" in values and Role.objects.for_organisation(
            organisation
        ).filter(name__iexact=values["name"]).exclude(pk=role.pk).exists():
            return Response(
                {"name": ["A role with this name already exists."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        permissions = values.pop("permission_ids", None)
        for field in ("name", "description", "is_active"):
            if field in values:
                setattr(role, field, values[field])
        role.save()
        if permissions is not None:
            replace_role_permissions(role, organisation, permissions)
        return Response(serialize_role(role))
