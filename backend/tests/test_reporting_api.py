import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.billing.models import ModuleEntitlement
from apps.organisations.models import Branch, Membership, Organisation
from apps.rbac.models import BranchGrant, Permission, Role, RolePermission
from apps.retail.models import Customer, Product, Sale, Shift, StockBalance


User = get_user_model()


def create_api_context(username, permissions):
    organisation = Organisation.objects.create(
        name=f"{username} organisation",
        sector=Organisation.Sector.RETAIL,
    )
    branch = Branch.objects.create(organisation=organisation, name="Main")
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="StrongPassword!42",
    )
    role = Role.objects.create(organisation=organisation, name=f"{username} role")
    membership = Membership.objects.create(
        organisation=organisation,
        user=user,
        role=role,
        status=Membership.Status.ACTIVE,
    )
    for code in permissions:
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
    BranchGrant.objects.create(
        organisation=organisation,
        membership=membership,
        branch=branch,
    )
    client = APIClient()
    client.force_login(user)
    client.defaults["HTTP_X_ORGANISATION_ID"] = str(organisation.pk)
    return organisation, branch, user, client


def create_product(organisation, username):
    product = Product.objects.create(
        organisation=organisation,
        name="Tea",
        sku=f"TEA-{username}",
        selling_price=Decimal("5.00"),
        cost_price=Decimal("4.00"),
        tax_rate=Decimal("0.00"),
    )
    return product


def checkout(client, branch, shift, product, payment_method, key, *, customer=None):
    payload = {
        "branch": str(branch.pk),
        "shift": str(shift.pk),
        "payment_method": payment_method,
        "lines": [{"product": str(product.pk), "quantity": "2.000"}],
    }
    if payment_method == Sale.PaymentMethod.CASH:
        payload["amount_tendered"] = "10.00"
    if customer is not None:
        payload["customer"] = str(customer.pk)
    response = client.post(
        reverse("retail:checkout"),
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(key),
    )
    assert response.status_code == 201, response.data
    return response.data


@pytest.mark.django_db
def test_shift_close_reconciles_cash_expenses_and_cash_refunds():
    permissions = [
        "retail.shifts.open",
        "retail.shifts.view",
        "retail.shifts.close",
        "retail.expenses.create",
        "retail.expenses.view",
        "retail.sales.checkout",
        "retail.sales.collection",
        "retail.sales.return",
    ]
    organisation, branch, user, client = create_api_context(
        "shift-reconcile",
        permissions,
    )
    product = create_product(organisation, "shift-reconcile")
    StockBalance.objects.create(
        organisation=organisation,
        branch=branch,
        product=product,
        quantity=Decimal("10.000"),
        average_cost=Decimal("4.00"),
    )

    opened = client.post(
        reverse("retail:shift-open"),
        {"branch": str(branch.pk), "opening_float": "100.00"},
        format="json",
    )
    assert opened.status_code == 201
    shift_id = opened.data["id"]
    shift = Shift.objects.get(pk=shift_id)
    sale = checkout(
        client,
        branch,
        shift,
        product,
        Sale.PaymentMethod.CASH,
        uuid.uuid4(),
    )
    customer = Customer.objects.create(
        organisation=organisation,
        name="Shift customer",
        credit_limit=Decimal("100.00"),
    )
    credit_sale = checkout(
        client,
        branch,
        shift,
        product,
        Sale.PaymentMethod.CREDIT,
        uuid.uuid4(),
        customer=customer,
    )
    checkout(
        client,
        branch,
        shift,
        product,
        Sale.PaymentMethod.MPESA,
        uuid.uuid4(),
    )
    collection = client.post(
        reverse(
            "retail:customer-collection",
            kwargs={"customer_pk": customer.pk},
        ),
        {
            "branch": str(branch.pk),
            "shift": str(shift.pk),
            "method": "cash",
            "amount": "10.00",
            "allocations": [{"sale": credit_sale["id"], "amount": "10.00"}],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert collection.status_code == 201, collection.data
    expense_key = uuid.uuid4()
    expense_payload = {
        "branch": str(branch.pk),
        "shift": str(shift.pk),
        "category": "Supplies",
        "description": "Receipt paper",
        "amount": "2.50",
        "payment_method": "cash",
    }
    expense_url = reverse("retail:expense-list")
    expense = client.post(
        expense_url,
        expense_payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(expense_key),
    )
    duplicate_expense = client.post(
        expense_url,
        expense_payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(expense_key),
    )
    assert expense.status_code == 201
    assert duplicate_expense.status_code == 200
    assert duplicate_expense.data["id"] == expense.data["id"]

    returned = client.post(
        reverse("retail:sale-return-create", kwargs={"pk": sale["id"]}),
        {
            "reason": "Damaged package",
            "refund_method": "cash",
            "lines": [
                {
                    "sale_line": sale["lines"][0]["id"],
                    "quantity": "1.000",
                }
            ],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert returned.status_code == 201, returned.data

    close_url = reverse("retail:shift-close", kwargs={"pk": shift_id})
    closed = client.post(
        close_url,
        {"counted_cash": "111.00"},
        format="json",
    )
    assert closed.status_code == 200
    assert closed.data["expected_cash"] == "112.50"
    assert closed.data["counted_cash"] == "111.00"
    assert closed.data["variance"] == "-1.50"
    repeated = client.post(
        close_url,
        {"counted_cash": "111.00"},
        format="json",
    )
    conflict = client.post(
        close_url,
        {"counted_cash": "112.00"},
        format="json",
    )
    assert repeated.status_code == 200
    assert conflict.status_code == 409


@pytest.mark.django_db
def test_reports_filter_by_date_and_branch_paginate_and_export_csv():
    permissions = [
        "retail.reports.view",
        "retail.sales.checkout",
        "retail.sales.return",
        "retail.expenses.create",
    ]
    organisation, branch, _, client = create_api_context(
        "reporting",
        permissions,
    )
    product = create_product(organisation, "reporting")
    balance = StockBalance.objects.create(
        organisation=organisation,
        branch=branch,
        product=product,
        quantity=Decimal("20.000"),
        average_cost=Decimal("4.00"),
    )
    shift = Shift.objects.create(
        organisation=organisation,
        branch=branch,
        cashier=User.objects.get(username="reporting"),
        opening_float=Decimal("100.00"),
    )
    customer = Customer.objects.create(
        organisation=organisation,
        name="Amina",
        phone_number="0712345678",
        credit_limit=Decimal("100.00"),
    )
    cash_sale = checkout(
        client,
        branch,
        shift,
        product,
        Sale.PaymentMethod.CASH,
        uuid.uuid4(),
    )
    credit_sale = checkout(
        client,
        branch,
        shift,
        product,
        Sale.PaymentMethod.CREDIT,
        uuid.uuid4(),
        customer=customer,
    )
    return_response = client.post(
        reverse("retail:sale-return-create", kwargs={"pk": cash_sale["id"]}),
        {
            "reason": "Damaged package",
            "refund_method": "mpesa",
            "lines": [
                {
                    "sale_line": cash_sale["lines"][0]["id"],
                    "quantity": "1.000",
                }
            ],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert return_response.status_code == 201, return_response.data
    Sale.objects.filter(pk=credit_sale["id"]).update(
        created_at=timezone.now() - timedelta(days=1)
    )
    expense = client.post(
        reverse("retail:expense-list"),
        {
            "branch": str(branch.pk),
            "shift": str(shift.pk),
            "category": "Utilities",
            "description": "Power",
            "amount": "1.00",
            "payment_method": "cash",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert expense.status_code == 201, expense.data

    query = {
        "branch_id": str(branch.pk),
        "from_date": (timezone.localdate() - timedelta(days=1)).isoformat(),
        "to_date": timezone.localdate().isoformat(),
        "page_size": "50",
    }
    summary = client.get(
        reverse("reporting:sales-summary"),
        query,
    )
    assert summary.status_code == 200
    assert summary.data["count"] == 2
    assert sum(row["sales_count"] for row in summary.data["results"]) == 2
    assert sum(row["gross_sales"] for row in summary.data["results"]) == Decimal(
        "20.00"
    )
    assert sum(
        row["returned_amount"] for row in summary.data["results"]
    ) == Decimal("5.00")
    assert sum(row["net_sales"] for row in summary.data["results"]) == Decimal(
        "15.00"
    )
    first_page = client.get(
        reverse("reporting:sales-summary"),
        {**query, "page_size": "1"},
    )
    assert first_page.data["count"] == 2
    assert first_page.data["next"] is not None
    csv_export = client.get(
        reverse("reporting:sales-summary"),
        {**query, "export": "csv"},
    )
    assert csv_export.status_code == 200
    assert csv_export["Content-Type"].startswith("text/csv")
    assert "Gross sales" in csv_export.content.decode()

    stock = client.get(reverse("reporting:stock"), query)
    assert stock.status_code == 200
    assert stock.data["results"][0]["opening_quantity"] == Decimal("20.000")
    assert stock.data["results"][0]["closing_quantity"] == Decimal("17.000")
    assert balance.quantity == Decimal("20.000")

    debt = client.get(reverse("reporting:customer-debt"), query)
    assert debt.status_code == 200
    assert debt.data["results"][0]["customer_id"] == str(customer.pk)
    assert debt.data["results"][0]["outstanding_balance"] == Decimal("10.00")

    expenses = client.get(reverse("reporting:expenses"), query)
    assert expenses.status_code == 200
    assert expenses.data["count"] == 1
    assert expenses.data["results"][0]["amount"] == Decimal("1.00")

    profit = client.get(reverse("reporting:profit"), query)
    assert profit.status_code == 200
    assert sum(row["net_sales"] for row in profit.data["results"]) == Decimal(
        "15.00"
    )
    assert sum(
        row["net_cost_of_goods_sold"] for row in profit.data["results"]
    ) == Decimal("12.00")
    assert sum(row["expenses"] for row in profit.data["results"]) == Decimal(
        "1.00"
    )
    assert sum(row["net_profit"] for row in profit.data["results"]) == Decimal(
        "2.00"
    )


@pytest.mark.django_db
def test_expense_and_report_filters_reject_foreign_tenant_resources():
    permissions = ["retail.expenses.create", "retail.reports.view"]
    organisation, branch, user, client = create_api_context(
        "tenant-report",
        permissions,
    )
    foreign_org = Organisation.objects.create(
        name="Foreign organisation",
        sector=Organisation.Sector.RETAIL,
    )
    foreign_branch = Branch.objects.create(
        organisation=foreign_org,
        name="Foreign branch",
    )
    shift = Shift.objects.create(
        organisation=organisation,
        branch=branch,
        cashier=user,
        opening_float=Decimal("0.00"),
    )
    response = client.post(
        reverse("retail:expense-list"),
        {
            "branch": str(foreign_branch.pk),
            "shift": str(shift.pk),
            "category": "Supplies",
            "amount": "1.00",
            "payment_method": "cash",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    foreign_report = client.get(
        reverse("reporting:stock"),
        {"branch_id": str(foreign_branch.pk)},
    )
    assert response.status_code == 403
    assert foreign_report.status_code == 403
