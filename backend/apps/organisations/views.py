from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organisations.models import Branch, Membership, Organisation
from apps.organisations.serializers import (
    MembershipCreateSerializer,
    MembershipUpdateSerializer,
    OrganisationCreateSerializer,
    OrganisationSerializer,
    serialize_membership,
)
from apps.rbac.models import BranchGrant, Permission, Role, RolePermission
from core.permissions import HasOrganisationPermission


ORGANISATION_PERMISSIONS = (
    ("organisations.manage", "Manage organisations"),
    ("staff.manage", "Manage staff"),
    ("rbac.manage", "Manage roles and permissions"),
)


class OrganisationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        memberships = (
            Membership.objects.select_related("organisation", "role")
            .filter(
                user=request.user,
                user__is_active=True,
                status=Membership.Status.ACTIVE,
                organisation__is_active=True,
                role__is_active=True,
            )
            .order_by("organisation__name")
        )
        return Response(
            {
                "results": [
                    {
                        **OrganisationSerializer(item.organisation).data,
                        "role": item.role.name,
                    }
                    for item in memberships
                ]
            }
        )

    @transaction.atomic
    def post(self, request):
        serializer = OrganisationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data

        base_slug = slugify(values["name"]) or "organisation"
        slug = base_slug
        suffix = 2
        while Organisation.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{suffix}"
            suffix += 1

        organisation = Organisation.objects.create(slug=slug, **values)
        role = Role.objects.create(
            organisation=organisation,
            name="Owner",
            description="Full access to this organisation.",
            is_system=True,
        )
        permissions = list(Permission.objects.filter(is_active=True))
        for codename, name in ORGANISATION_PERMISSIONS:
            permission, _ = Permission.objects.get_or_create(
                codename=codename,
                defaults={
                    "name": name,
                    "module": Permission.Module.PLATFORM,
                },
            )
            if permission.is_active:
                permissions.append(permission)
        unique_permissions = {
            permission.pk: permission for permission in permissions
        }.values()
        RolePermission.objects.bulk_create(
            [
                RolePermission(
                    organisation=organisation,
                    role=role,
                    permission=permission,
                )
                for permission in unique_permissions
            ]
        )
        Membership.objects.create(
            organisation=organisation,
            user=request.user,
            role=role,
            status=Membership.Status.ACTIVE,
            all_branches=True,
            joined_at=timezone.now(),
        )
        return Response(
            OrganisationSerializer(organisation).data,
            status=status.HTTP_201_CREATED,
        )


class MembershipListCreateView(APIView):
    permission_classes = [IsAuthenticated, HasOrganisationPermission]
    required_permission = "staff.manage"

    def get(self, request):
        organisation = request.active_organisation
        memberships = (
            Membership.objects.for_organisation(organisation)
            .select_related("user", "role")
            .order_by("user__email")
        )
        return Response(
            {"results": [serialize_membership(item) for item in memberships]}
        )

    @transaction.atomic
    def post(self, request):
        organisation = request.active_organisation
        serializer = MembershipCreateSerializer(
            data=request.data,
            context={"organisation": organisation},
        )
        serializer.is_valid(raise_exception=True)
        membership = Membership.objects.create(
            organisation=organisation,
            user=serializer.validated_data["user"],
            role=serializer.validated_data["role"],
            status=Membership.Status.ACTIVE,
            all_branches=serializer.validated_data["all_branches"],
            joined_at=timezone.now(),
        )
        BranchGrant.objects.bulk_create(
            [
                BranchGrant(
                    organisation=organisation,
                    membership=membership,
                    branch_id=branch_id,
                )
                for branch_id in serializer.validated_data["branch_ids"]
            ]
        )
        return Response(
            serialize_membership(membership),
            status=status.HTTP_201_CREATED,
        )


class MembershipDetailView(APIView):
    permission_classes = [IsAuthenticated, HasOrganisationPermission]
    required_permission = "staff.manage"

    @transaction.atomic
    def patch(self, request, membership_id):
        organisation = request.active_organisation
        membership = (
            Membership.objects.for_organisation(organisation)
            .select_related("user", "role")
            .filter(pk=membership_id)
            .first()
        )
        if membership is None:
            return Response(
                {"detail": "Staff membership not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if membership.user_id == request.user.pk:
            return Response(
                {"detail": "You cannot change your own organisation membership."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = MembershipUpdateSerializer(
            data=request.data,
            context={"organisation": organisation, "membership": membership},
        )
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        if "role_id" in values:
            membership.role = values["role_id"]
        if "status" in values:
            membership.status = values["status"]
        if "all_branches" in values:
            membership.all_branches = values["all_branches"]
        membership.save()
        if membership.all_branches:
            membership.branch_grants.all().delete()
        elif "branch_ids" in values:
            BranchGrant.objects.for_organisation(organisation).filter(
                membership=membership
            ).delete()
            BranchGrant.objects.bulk_create(
                [
                    BranchGrant(
                        organisation=organisation,
                        membership=membership,
                        branch_id=branch_id,
                    )
                    for branch_id in values["branch_ids"]
                ]
            )
        return Response(serialize_membership(membership))


class BranchListView(APIView):
    permission_classes = [IsAuthenticated, HasOrganisationPermission]
    required_permission = "staff.manage"

    def get(self, request):
        branches = Branch.objects.for_organisation(
            request.active_organisation
        ).filter(is_active=True)
        return Response(
            {
                "results": [
                    {"id": str(branch.pk), "name": branch.name, "code": branch.code}
                    for branch in branches
                ]
            }
        )
