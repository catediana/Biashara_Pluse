import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from apps.billing.models import ModuleEntitlement
from apps.organisations.models import Branch, Membership, Organisation
from apps.rbac.models import BranchGrant, Permission, Role, RolePermission
from core.permissions import HasBranchAccess, HasTenantAccess
from core.tenancy import scope_queryset


User = get_user_model()


class TenantAccessProbe(APIView):
    permission_classes = [HasTenantAccess]
    required_permission = "retail.sales.read"
    required_module = "retail"
    branch_scoped = True

    def get(self, request):
        return Response(
            {
                "allowed": True,
                "organisation_id": str(request.active_organisation.pk),
            }
        )


def create_organisation(name):
    return Organisation.objects.create(
        name=name,
        sector=Organisation.Sector.RETAIL,
    )


def create_user(username):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="StrongPassword!42",
    )


def grant_retail_access(user, organisation, branch, *, all_branches=False):
    role = Role.objects.create(organisation=organisation, name="Cashier")
    membership = Membership.objects.create(
        organisation=organisation,
        user=user,
        role=role,
        status=Membership.Status.ACTIVE,
        all_branches=all_branches,
    )
    permission, _ = Permission.objects.get_or_create(
        codename="retail.sales.read",
        defaults={"name": "View retail sales", "module": Permission.Module.RETAIL},
    )
    RolePermission.objects.create(
        organisation=organisation,
        role=role,
        permission=permission,
    )
    ModuleEntitlement.objects.create(
        organisation=organisation,
        module=ModuleEntitlement.Module.RETAIL,
    )
    if branch is not None and not all_branches:
        BranchGrant.objects.create(
            organisation=organisation,
            membership=membership,
            branch=branch,
        )
    return membership


def request_probe(user, organisation, branch_id):
    request = APIRequestFactory().get(
        "/tenant-probe/",
        {"branch": str(branch_id)},
    )
    request.active_organisation = organisation
    force_authenticate(request, user=user)
    return TenantAccessProbe.as_view()(request)


@pytest.mark.django_db
def test_tenant_queryset_filters_records_and_rejects_missing_organisation():
    first = create_organisation("First shop")
    second = create_organisation("Second shop")
    first_branch = Branch.objects.create(organisation=first, name="Main")
    Branch.objects.create(organisation=second, name="Main")

    assert list(scope_queryset(Branch.objects.all(), first)) == [first_branch]
    with pytest.raises(ValueError):
        Branch.objects.for_organisation(None)


@pytest.mark.django_db
def test_member_cannot_access_another_organisations_data():
    first = create_organisation("First shop")
    second = create_organisation("Second shop")
    branch = Branch.objects.create(organisation=first, name="Main")
    outsider = create_user("outsider")
    other_branch = Branch.objects.create(organisation=second, name="Main")
    grant_retail_access(
        outsider,
        second,
        other_branch,
        all_branches=True,
    )

    response = request_probe(outsider, first, branch.pk)

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_branch_grant_and_module_entitlement_are_enforced():
    organisation = create_organisation("Retail shop")
    assigned_branch = Branch.objects.create(
        organisation=organisation,
        name="Assigned",
    )
    other_branch = Branch.objects.create(
        organisation=organisation,
        name="Unassigned",
    )
    user = create_user("cashier")
    grant_retail_access(user, organisation, assigned_branch)

    assert (
        request_probe(user, organisation, assigned_branch.pk).status_code
        == status.HTTP_200_OK
    )
    assert (
        request_probe(user, organisation, other_branch.pk).status_code
        == status.HTTP_403_FORBIDDEN
    )

    ModuleEntitlement.objects.filter(organisation=organisation).update(
        is_enabled=False
    )
    assert (
        request_probe(user, organisation, assigned_branch.pk).status_code
        == status.HTTP_403_FORBIDDEN
    )


@pytest.mark.django_db
def test_cross_organisation_membership_and_branch_grants_are_rejected():
    first = create_organisation("First shop")
    second = create_organisation("Second shop")
    first_branch = Branch.objects.create(organisation=first, name="Main")
    second_branch = Branch.objects.create(organisation=second, name="Main")
    user = create_user("manager")
    first_role = Role.objects.create(organisation=first, name="Manager")
    second_role = Role.objects.create(organisation=second, name="Manager")
    first_membership = Membership.objects.create(
        organisation=first,
        user=user,
        role=first_role,
        status=Membership.Status.ACTIVE,
    )

    with pytest.raises(ValidationError):
        Membership.objects.create(
            organisation=first,
            user=create_user("other-manager"),
            role=second_role,
            status=Membership.Status.ACTIVE,
        )
    with pytest.raises(ValidationError):
        BranchGrant.objects.create(
            organisation=first,
            membership=first_membership,
            branch=second_branch,
        )

    assert first_branch.organisation_id != second_branch.organisation_id


@pytest.mark.django_db
def test_membership_without_role_permission_is_denied():
    organisation = create_organisation("Retail shop")
    branch = Branch.objects.create(organisation=organisation, name="Main")
    user = create_user("unprivileged")
    role = Role.objects.create(organisation=organisation, name="No access")
    Membership.objects.create(
        organisation=organisation,
        user=user,
        role=role,
        status=Membership.Status.ACTIVE,
    )
    ModuleEntitlement.objects.create(
        organisation=organisation,
        module=ModuleEntitlement.Module.RETAIL,
    )

    response = request_probe(user, organisation, branch.pk)

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_branch_access_permission_rejects_missing_branch_for_limited_member():
    organisation = create_organisation("Retail shop")
    branch = Branch.objects.create(organisation=organisation, name="Main")
    user = create_user("limited")
    membership = grant_retail_access(user, organisation, branch)
    request = APIRequestFactory().get("/tenant-probe/")
    request.active_organisation = organisation
    force_authenticate(request, user=user)
    drf_request = TenantAccessProbe().initialize_request(request)

    assert not HasBranchAccess().has_permission(drf_request, TenantAccessProbe())
    assert membership.all_branches is False
