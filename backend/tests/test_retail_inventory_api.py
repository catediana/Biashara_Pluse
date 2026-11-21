import uuid
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.billing.models import ModuleEntitlement
from apps.organisations.models import Branch, Membership, Organisation
from apps.rbac.models import BranchGrant, Permission, Role, RolePermission
from apps.retail.models import (
    GoodsReceipt,
    Product,
    StockAdjustment,
    StockBalance,
    StockMovement,
    Supplier,
)


def create_organisation(name):
    return Organisation.objects.create(
        name=name,
        sector=Organisation.Sector.RETAIL,
    )


def create_user(username):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="StrongPassword!42",
    )


def create_member(user, organisation, branch, permission_codes):
    role = Role.objects.create(organisation=organisation, name=f"{user.username} role")
    Membership.objects.create(
        organisation=organisation,
        user=user,
        role=role,
        status=Membership.Status.ACTIVE,
    )
    for code in permission_codes:
        permission, _ = Permission.objects.get_or_create(
            codename=code,
            defaults={
                "name": code.replace(".", " ").title(),
                "module": Permission.Module.RETAIL,
            },
        )
        RolePermission.objects.create(
            organisation=organisation,
            role=role,
            permission=permission,
        )
    ModuleEntitlement.objects.get_or_create(
        organisation=organisation,
        module=ModuleEntitlement.Module.RETAIL,
    )
    if branch is not None:
        BranchGrant.objects.create(
            organisation=organisation,
            membership=Membership.objects.get(
                organisation=organisation,
                user=user,
            ),
            branch=branch,
        )
    return role


def client_for(user, organisation):
    client = APIClient()
    client.force_login(user)
    client.defaults["HTTP_X_ORGANISATION_ID"] = str(organisation.pk)
    return client


def create_product(organisation, **overrides):
    fields = {
        "organisation": organisation,
        "name": "Tea",
        "sku": "TEA-001",
        "barcode": "123456789",
        "unit": "each",
        "selling_price": Decimal("4.00"),
        "cost_price": Decimal("2.00"),
        "tax_rate": Decimal("0.00"),
        "reorder_level": Decimal("2.000"),
    }
    fields.update(overrides)
    return Product.objects.create(**fields)


def receipt_payload(branch, supplier, product, quantity="10.000"):
    return {
        "branch": str(branch.pk),
        "supplier": str(supplier.pk),
        "supplier_reference": "INV-001",
        "lines": [
            {
                "product": str(product.pk),
                "quantity": quantity,
                "unit_cost": "2.50",
            }
        ],
    }


@pytest.mark.django_db
def test_product_catalogue_search_and_cross_tenant_retrieval():
    organisation = create_organisation("Retail A")
    branch = Branch.objects.create(organisation=organisation, name="Main")
    user = create_user("catalogue")
    create_member(
        user,
        organisation,
        branch,
        ["retail.products.view", "retail.products.create", "retail.products.update"],
    )
    client = client_for(user, organisation)

    response = client.post(
        reverse("retail:product-list"),
        {
            "name": "Black tea",
            "sku": "TEA-001",
            "barcode": "123456789",
            "selling_price": "4.50",
            "cost_price": "2.25",
            "tax_rate": "16.00",
            "reorder_level": "5.000",
        },
        format="json",
    )
    assert response.status_code == 201
    product_id = response.json()["id"]

    response = client.get(
        reverse("retail:product-list"),
        {"search": "TEA-001"},
    )
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["id"] == product_id

    other_organisation = create_organisation("Retail B")
    foreign_product = create_product(
        other_organisation,
        name="Foreign tea",
        sku="FOREIGN-1",
        barcode="987654321",
    )
    response = client.get(
        reverse("retail:product-detail", kwargs={"pk": foreign_product.pk})
    )
    assert response.status_code == 404

    client.defaults["HTTP_X_ORGANISATION_ID"] = str(other_organisation.pk)
    assert client.get(reverse("retail:product-list")).status_code == 403


@pytest.mark.django_db
def test_goods_receipt_is_atomic_and_idempotent():
    organisation = create_organisation("Receiving shop")
    branch = Branch.objects.create(organisation=organisation, name="Main")
    supplier = Supplier.objects.create(organisation=organisation, name="Tea Co")
    product = create_product(organisation)
    user = create_user("receiver")
    create_member(user, organisation, branch, ["retail.stock.receive"])
    client = client_for(user, organisation)
    url = reverse("retail:goods-receipt-create")
    key = str(uuid.uuid4())
    payload = receipt_payload(branch, supplier, product)

    response = client.post(
        url,
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )
    assert response.status_code == 201
    receipt_id = response.json()["id"]
    balance = StockBalance.objects.get(
        organisation=organisation,
        branch=branch,
        product=product,
    )
    assert balance.quantity == Decimal("10.000")
    assert balance.average_cost == Decimal("2.50")
    assert balance.version == 2
    assert response.json()["total_cost"] == "25.00"

    duplicate = client.post(
        url,
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["id"] == receipt_id
    balance.refresh_from_db()
    assert balance.quantity == Decimal("10.000")
    assert GoodsReceipt.objects.for_organisation(organisation).count() == 1
    assert StockMovement.objects.for_organisation(organisation).count() == 1

    conflict = client.post(
        url,
        receipt_payload(branch, supplier, product, quantity="11.000"),
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )
    assert conflict.status_code == 409
    balance.refresh_from_db()
    assert balance.quantity == Decimal("10.000")


@pytest.mark.django_db
@pytest.mark.parametrize("quantity", ["0.000", "-1.000"])
def test_goods_receipt_rejects_nonpositive_quantity(quantity):
    organisation = create_organisation("Invalid receiving shop")
    branch = Branch.objects.create(organisation=organisation, name="Main")
    supplier = Supplier.objects.create(organisation=organisation, name="Tea Co")
    product = create_product(organisation)
    user = create_user(f"receiver-{quantity[0]}")
    create_member(user, organisation, branch, ["retail.stock.receive"])
    client = client_for(user, organisation)

    response = client.post(
        reverse("retail:goods-receipt-create"),
        receipt_payload(branch, supplier, product, quantity=quantity),
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )

    assert response.status_code == 400
    assert GoodsReceipt.objects.for_organisation(organisation).count() == 0
    assert StockBalance.objects.for_organisation(organisation).count() == 0
    assert StockMovement.objects.for_organisation(organisation).count() == 0


@pytest.mark.django_db
def test_stock_adjustment_requires_approval_and_prevents_negative_stock():
    organisation = create_organisation("Adjustment shop")
    branch = Branch.objects.create(organisation=organisation, name="Main")
    product = create_product(organisation)
    StockBalance.objects.create(
        organisation=organisation,
        branch=branch,
        product=product,
        quantity=Decimal("5.000"),
        average_cost=Decimal("2.00"),
        version=1,
    )

    clerk = create_user("stock-clerk")
    create_member(
        clerk,
        organisation,
        branch,
        ["retail.stock.adjustment.request"],
    )
    manager = create_user("stock-manager")
    create_member(
        manager,
        organisation,
        branch,
        ["retail.stock.adjustment.approve", "retail.stock.adjustment.reject"],
    )
    clerk_client = client_for(clerk, organisation)
    manager_client = client_for(manager, organisation)
    url = reverse("retail:stock-adjustment-create")
    key = str(uuid.uuid4())
    payload = {
        "branch": str(branch.pk),
        "product": str(product.pk),
        "quantity_delta": "-2.000",
        "expected_stock_version": 1,
        "reason": "Damaged stock",
    }

    response = clerk_client.post(
        url,
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )
    assert response.status_code == 201
    adjustment_id = response.json()["id"]
    assert response.json()["status"] == StockAdjustment.Status.REQUESTED
    assert StockBalance.objects.get(product=product).quantity == Decimal("5.000")

    duplicate = clerk_client.post(
        url,
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )
    assert duplicate.status_code == 200
    assert StockAdjustment.objects.for_organisation(organisation).count() == 1

    approval_url = reverse(
        "retail:stock-adjustment-decision",
        kwargs={"pk": adjustment_id, "action": "approve"},
    )
    approved = manager_client.post(approval_url, {}, format="json")
    assert approved.status_code == 200
    assert approved.json()["status"] == StockAdjustment.Status.APPROVED
    balance = StockBalance.objects.get(product=product)
    assert balance.quantity == Decimal("3.000")
    assert balance.version == 2
    assert StockMovement.objects.filter(stock_adjustment_id=adjustment_id).count() == 1

    duplicate_approval = manager_client.post(approval_url, {}, format="json")
    assert duplicate_approval.status_code == 200
    assert StockMovement.objects.filter(stock_adjustment_id=adjustment_id).count() == 1

    stale = clerk_client.post(
        url,
        {
            **payload,
            "quantity_delta": "-1.000",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert stale.status_code == 409

    negative_key = str(uuid.uuid4())
    negative_adjustment = clerk_client.post(
        url,
        {
            **payload,
            "quantity_delta": "-5.000",
            "expected_stock_version": 2,
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=negative_key,
    )
    assert negative_adjustment.status_code == 201
    negative_approval_url = reverse(
        "retail:stock-adjustment-decision",
        kwargs={
            "pk": negative_adjustment.json()["id"],
            "action": "approve",
        },
    )
    rejected_by_rule = manager_client.post(
        negative_approval_url,
        {},
        format="json",
    )
    assert rejected_by_rule.status_code == 422
    balance.refresh_from_db()
    assert balance.quantity == Decimal("3.000")


@pytest.mark.django_db
def test_goods_receipt_rejects_foreign_tenant_branch():
    organisation = create_organisation("First shop")
    foreign_organisation = create_organisation("Second shop")
    branch = Branch.objects.create(
        organisation=foreign_organisation,
        name="Foreign branch",
    )
    supplier = Supplier.objects.create(
        organisation=organisation,
        name="Local supplier",
    )
    product = create_product(organisation)
    user = create_user("foreign-branch-receiver")
    create_member(user, organisation, None, ["retail.stock.receive"])
    client = client_for(user, organisation)

    response = client.post(
        reverse("retail:goods-receipt-create"),
        receipt_payload(branch, supplier, product),
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )

    assert response.status_code == 403
    assert GoodsReceipt.objects.for_organisation(organisation).count() == 0
