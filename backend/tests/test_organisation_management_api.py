import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.organisations.models import Branch, Membership, Organisation
from apps.rbac.models import Permission, Role, RolePermission


User = get_user_model()


def create_user(username, email=None):
    return User.objects.create_user(
        username=username,
        email=email or f"{username}@example.com",
        password="StrongPassword!42",
    )


def client_for(user, organisation=None):
    client = APIClient()
    client.force_login(user)
    if organisation is not None:
        client.defaults["HTTP_X_ORGANISATION_ID"] = str(organisation.pk)
    return client


@pytest.mark.django_db
def test_create_organisation_provisions_owner_and_list_is_user_scoped():
    owner = create_user("owner")
    other_user = create_user("other")
    client = client_for(owner)

    response = client.post(
        "/api/organisations/",
        {
            "name": "  Greenview   Traders ",
            "sector": "retail",
            "country_code": "ke",
            "currency": "kes",
            "timezone": "Africa/Nairobi",
        },
        format="json",
    )

    assert response.status_code == 201
    organisation = Organisation.objects.get(pk=response.data["id"])
    membership = Membership.objects.get(organisation=organisation, user=owner)
    assert organisation.name == "Greenview Traders"
    assert organisation.slug == "greenview-traders"
    assert membership.role.is_system is True
    assert membership.status == Membership.Status.ACTIVE
    assert membership.role.permissions.filter(
        codename="retail.products.view"
    ).exists()
    assert client.get("/api/organisations/").data["results"][0]["id"] == str(
        organisation.pk
    )
    assert client_for(other_user).get("/api/organisations/").data["results"] == []


@pytest.mark.django_db
def test_staff_and_roles_endpoints_are_tenant_scoped_and_manage_permissions():
    owner = create_user("owner")
    organisation = Organisation.objects.create(
        name="North Shop",
        sector=Organisation.Sector.RETAIL,
    )
    owner_role = Role.objects.create(
        organisation=organisation,
        name="Owner",
        is_system=True,
    )
    Membership.objects.create(
        organisation=organisation,
        user=owner,
        role=owner_role,
        status=Membership.Status.ACTIVE,
    )
    for code in ("staff.manage", "rbac.manage"):
        permission, _ = Permission.objects.get_or_create(
            codename=code,
            defaults={
                "name": code.replace(".", " ").title(),
                "module": Permission.Module.PLATFORM,
            },
        )
        RolePermission.objects.create(
            organisation=organisation,
            role=owner_role,
            permission=permission,
        )

    client = client_for(owner, organisation)
    branch = Branch.objects.create(organisation=organisation, name="Main")
    role_response = client.post(
        "/api/rbac/roles/",
        {
            "name": "Cashier",
            "description": "Point-of-sale staff",
            "permission_ids": [],
        },
        format="json",
    )
    assert role_response.status_code == 201
    staff_user = create_user("cashier")
    staff_response = client.post(
        "/api/organisations/members/",
        {
            "email": staff_user.email,
            "role_id": role_response.data["id"],
            "all_branches": False,
            "branch_ids": [str(branch.pk)],
        },
        format="json",
    )
    assert staff_response.status_code == 201
    assert staff_response.data["role"]["name"] == "Cashier"
    assert staff_response.data["branch_ids"] == [str(branch.pk)]
    assert client.get("/api/organisations/members/").data["results"][0]["user"][
        "email"
    ] == staff_user.email
    update_response = client.patch(
        f"/api/organisations/members/{staff_response.data['id']}/",
        {"all_branches": True},
        format="json",
    )
    assert update_response.status_code == 200
    assert update_response.data["branch_ids"] == []

    another_organisation = Organisation.objects.create(
        name="South Shop",
        sector=Organisation.Sector.RETAIL,
    )
    outsider = create_user("outsider")
    outsider_role = Role.objects.create(
        organisation=another_organisation,
        name="Owner",
    )
    Membership.objects.create(
        organisation=another_organisation,
        user=outsider,
        role=outsider_role,
        status=Membership.Status.ACTIVE,
    )
    foreign_client = client_for(outsider, another_organisation)
    assert foreign_client.get("/api/organisations/members/").status_code == 403
    assert foreign_client.get("/api/rbac/roles/").status_code == 403


@pytest.mark.django_db
def test_staff_creation_rejects_unknown_email_and_cross_organisation_role():
    manager = create_user("manager")
    first = Organisation.objects.create(name="First", sector="retail")
    second = Organisation.objects.create(name="Second", sector="retail")
    role = Role.objects.create(organisation=first, name="Owner", is_system=True)
    permission, _ = Permission.objects.get_or_create(
        codename="staff.manage",
        defaults={
            "name": "Manage staff",
            "module": Permission.Module.PLATFORM,
        },
    )
    RolePermission.objects.create(
        organisation=first,
        role=role,
        permission=permission,
    )
    Membership.objects.create(
        organisation=first,
        user=manager,
        role=role,
        status=Membership.Status.ACTIVE,
    )
    foreign_role = Role.objects.create(organisation=second, name="Cashier")
    client = client_for(manager, first)

    unknown_user = client.post(
        "/api/organisations/members/",
        {
            "email": "missing@example.com",
            "role_id": str(foreign_role.pk),
            "all_branches": True,
        },
        format="json",
    )
    assert unknown_user.status_code == 400

    staff_user = create_user("staff")
    foreign_role_response = client.post(
        "/api/organisations/members/",
        {
            "email": staff_user.email,
            "role_id": str(foreign_role.pk),
            "all_branches": True,
        },
        format="json",
    )
    assert foreign_role_response.status_code == 400
