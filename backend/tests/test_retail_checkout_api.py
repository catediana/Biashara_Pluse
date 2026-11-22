import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.db.models import Sum
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.billing.models import ModuleEntitlement
from apps.organisations.models import Branch, Membership, Organisation
from apps.rbac.models import BranchGrant, Permission, Role, RolePermission
from apps.retail.models import (
    Customer,
    MpesaProviderEvent,
    Payment,
    PaymentAllocation,
    Product,
    Refund,
    Receipt,
    Sale,
    SaleLine,
    SaleReturn,
    Shift,
    StockBalance,
    StockMovement,
)


User = get_user_model()
CHECKOUT_PERMISSION = "retail.sales.checkout"
SALES_VIEW_PERMISSION = "retail.sales.view"
PAYMENT_PERMISSIONS = [
    "retail.sales.payment",
    "retail.sales.collection",
    "retail.sales.return",
    "retail.sales.refund",
    "retail.customers.view",
    "retail.customers.create",
]


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


def grant_retail_access(user, organisation, branch, permissions):
    role = Role.objects.create(organisation=organisation, name=f"{user.username} role")
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


def create_checkout_context(
    username="cashier",
    stock="5.000",
    extra_permissions=(),
):
    organisation = create_organisation(f"{username} shop")
    branch = Branch.objects.create(organisation=organisation, name="Main")
    user = create_user(username)
    grant_retail_access(
        user,
        organisation,
        branch,
        [CHECKOUT_PERMISSION, SALES_VIEW_PERMISSION, *extra_permissions],
    )
    shift = Shift.objects.create(
        organisation=organisation,
        branch=branch,
        cashier=user,
        opening_float=Decimal("100.00"),
    )
    product = Product.objects.create(
        organisation=organisation,
        name="Black tea",
        sku=f"TEA-{username}",
        barcode=f"123-{username}",
        selling_price=Decimal("4.00"),
        cost_price=Decimal("2.00"),
        tax_rate=Decimal("16.00"),
    )
    StockBalance.objects.create(
        organisation=organisation,
        branch=branch,
        product=product,
        quantity=Decimal(stock),
        average_cost=Decimal("2.00"),
    )
    client = APIClient()
    client.force_login(user)
    client.defaults["HTTP_X_ORGANISATION_ID"] = str(organisation.pk)
    return organisation, branch, user, shift, product, client


def checkout_payload(branch, shift, product, *, quantity="2.000", payment="cash"):
    return {
        "branch": str(branch.pk),
        "shift": str(shift.pk),
        "payment_method": payment,
        "amount_tendered": "10.00" if payment == "cash" else None,
        "lines": [{"product": str(product.pk), "quantity": quantity}],
    }


def post_checkout(client, payload, key=None):
    return client.post(
        reverse("retail:checkout"),
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()),
    )


@pytest.mark.django_db
def test_cash_checkout_creates_sale_receipt_stock_movement_and_audit_atomically():
    organisation, branch, user, shift, product, client = create_checkout_context()

    response = post_checkout(
        client,
        checkout_payload(branch, shift, product),
    )

    assert response.status_code == 201
    result = response.json()
    sale = Sale.objects.get(pk=result["id"])
    assert sale.status == Sale.Status.POSTED
    assert sale.payment_method == Sale.PaymentMethod.CASH
    assert sale.subtotal == Decimal("8.00")
    assert sale.tax_total == Decimal("1.28")
    assert sale.total == Decimal("9.28")
    assert sale.change_due == Decimal("0.72")
    assert result["lines"][0]["product_name"] == "Black tea"
    assert result["receipt"]["status"] == Receipt.Status.ISSUED
    assert result["receipt"]["snapshot"]["total"] == "9.28"

    balance = StockBalance.objects.get(
        organisation=organisation,
        branch=branch,
        product=product,
    )
    assert balance.quantity == Decimal("3.000")
    assert balance.version == 2
    movement = StockMovement.objects.get(sale=sale)
    assert movement.quantity_delta == Decimal("-2.000")
    assert movement.created_by_id == user.pk
    event = AuditEvent.objects.get(target_id=str(sale.pk))
    assert event.action == "retail.sale.checkout"
    assert event.correlation_id == sale.idempotency_key
    assert SaleLine.objects.filter(sale=sale).count() == 1
    assert Receipt.objects.filter(sale=sale).count() == 1


@pytest.mark.django_db
def test_mpesa_checkout_is_pending_until_verified():
    organisation, branch, _, shift, product, client = create_checkout_context(
        username="mpesa-cashier"
    )
    product.selling_price = Decimal("5.00")
    product.tax_rate = Decimal("0.00")
    product.save()

    response = post_checkout(
        client,
        checkout_payload(
            branch,
            shift,
            product,
            payment="mpesa",
        ),
    )

    assert response.status_code == 201, response.data
    sale = Sale.objects.get(pk=response.json()["id"])
    assert sale.status == Sale.Status.PENDING_PAYMENT
    assert sale.completed_at is None
    assert sale.amount_tendered is None
    assert response.json()["receipt"]["status"] == Receipt.Status.PENDING_PAYMENT
    assert response.json()["receipt"]["snapshot"]["payments"][0]["status"] == (
        Payment.Status.PENDING
    )
    assert StockBalance.objects.get(
        organisation=organisation,
        branch=branch,
        product=product,
    ).quantity == Decimal("3.000")


@pytest.mark.django_db
def test_insufficient_stock_and_invalid_cash_tender_leave_no_checkout_records():
    organisation, branch, _, shift, product, client = create_checkout_context(
        username="limited-cashier",
        stock="1.000",
    )

    response = post_checkout(
        client,
        checkout_payload(branch, shift, product, quantity="2.000"),
    )
    assert response.status_code == 422

    response = post_checkout(
        client,
        {
            **checkout_payload(branch, shift, product, quantity="1.000"),
            "amount_tendered": "1.00",
        },
    )
    assert response.status_code == 422
    assert Sale.objects.for_organisation(organisation).count() == 0
    assert Receipt.objects.for_organisation(organisation).count() == 0
    assert StockMovement.objects.for_organisation(organisation).count() == 0
    assert AuditEvent.objects.for_organisation(organisation).count() == 0
    assert StockBalance.objects.get(product=product).quantity == Decimal("1.000")


@pytest.mark.django_db
def test_checkout_duplicate_key_returns_original_sale_without_reducing_stock_again():
    organisation, branch, _, shift, product, client = create_checkout_context(
        username="retry-cashier"
    )
    key = str(uuid.uuid4())
    payload = checkout_payload(branch, shift, product)

    first = post_checkout(client, payload, key)
    duplicate = post_checkout(client, payload, key)

    assert first.status_code == 201
    assert duplicate.status_code == 200
    assert duplicate.json()["id"] == first.json()["id"]
    assert Sale.objects.for_organisation(organisation).count() == 1
    assert SaleLine.objects.for_organisation(organisation).count() == 1
    assert Receipt.objects.for_organisation(organisation).count() == 1
    assert StockMovement.objects.for_organisation(organisation).count() == 1
    assert AuditEvent.objects.for_organisation(organisation).count() == 1
    assert StockBalance.objects.get(product=product).quantity == Decimal("3.000")

    shift.status = Shift.Status.CLOSED
    from django.utils import timezone

    shift.closed_at = timezone.now()
    shift.save()
    retry_after_shift_closed = post_checkout(client, payload, key)
    assert retry_after_shift_closed.status_code == 200
    assert retry_after_shift_closed.json()["id"] == first.json()["id"]

    conflict = post_checkout(
        client,
        checkout_payload(branch, shift, product, quantity="1.000"),
        key,
    )
    assert conflict.status_code == 409
    assert Sale.objects.for_organisation(organisation).count() == 1


@pytest.mark.django_db
def test_checkout_rejects_closed_shift_and_unsupported_payment_method():
    organisation, branch, _, shift, product, client = create_checkout_context(
        username="closed-shift-cashier"
    )
    shift.status = Shift.Status.CLOSED
    from django.utils import timezone

    shift.closed_at = timezone.now()
    shift.save()

    response = post_checkout(
        client,
        checkout_payload(branch, shift, product),
    )
    assert response.status_code == 422

    shift.status = Shift.Status.OPEN
    shift.closed_at = None
    shift.save()
    response = post_checkout(
        client,
        {
            **checkout_payload(branch, shift, product),
            "payment_method": "cheque",
        },
    )
    assert response.status_code == 400
    assert Sale.objects.for_organisation(organisation).count() == 0


@pytest.mark.django_db
def test_sale_receipt_is_not_visible_from_another_tenant():
    organisation, branch, _, shift, product, client = create_checkout_context(
        username="tenant-one-cashier"
    )
    response = post_checkout(client, checkout_payload(branch, shift, product))
    sale_id = response.json()["id"]

    foreign_org = create_organisation("Foreign shop")
    foreign_branch = Branch.objects.create(
        organisation=foreign_org,
        name="Foreign branch",
    )
    foreign_user = create_user("tenant-two-cashier")
    grant_retail_access(
        foreign_user,
        foreign_org,
        foreign_branch,
        [CHECKOUT_PERMISSION, SALES_VIEW_PERMISSION],
    )
    foreign_client = APIClient()
    foreign_client.force_login(foreign_user)
    foreign_client.defaults["HTTP_X_ORGANISATION_ID"] = str(foreign_org.pk)

    response = foreign_client.get(
        reverse("retail:sale-receipt", kwargs={"pk": sale_id})
    )
    assert response.status_code == 404
    assert Sale.objects.for_organisation(foreign_org).count() == 0
    assert Sale.objects.for_organisation(organisation).count() == 1


@pytest.mark.django_db
def test_checkout_rejects_foreign_tenant_product_without_side_effects():
    organisation, branch, _, shift, product, client = create_checkout_context(
        username="cross-tenant-checkout-cashier"
    )
    foreign_org = create_organisation("Foreign catalogue")
    foreign_product = Product.objects.create(
        organisation=foreign_org,
        name="Foreign tea",
        sku="FOREIGN-TEA",
        selling_price=Decimal("3.00"),
        cost_price=Decimal("1.00"),
    )

    response = post_checkout(
        client,
        checkout_payload(branch, shift, foreign_product),
    )

    assert response.status_code == 400
    assert Sale.objects.for_organisation(organisation).count() == 0
    assert StockBalance.objects.get(product=product).quantity == Decimal("5.000")
    assert StockMovement.objects.for_organisation(organisation).count() == 0
    assert AuditEvent.objects.for_organisation(organisation).count() == 0


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(
    not connection.features.has_select_for_update,
    reason="Concurrent checkout locking requires database row-level locks.",
)
def test_concurrent_checkouts_cannot_oversell_stock():
    organisation, branch, user, shift, product, _ = create_checkout_context(
        username="concurrent-cashier",
        stock="1.000",
    )
    barrier = threading.Barrier(2)
    keys = [str(uuid.uuid4()), str(uuid.uuid4())]

    def submit(key):
        close_old_connections()
        client = APIClient()
        client.force_login(user)
        client.defaults["HTTP_X_ORGANISATION_ID"] = str(organisation.pk)
        barrier.wait()
        response = post_checkout(
            client,
            checkout_payload(branch, shift, product, quantity="1.000"),
            key,
        )
        close_old_connections()
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(submit, keys))

    assert sorted(outcomes) == [201, 422]
    assert Sale.objects.for_organisation(organisation).count() == 1
    assert StockBalance.objects.get(product=product).quantity == Decimal("0.000")


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(
    not connection.features.has_select_for_update,
    reason="Concurrent checkout locking requires database row-level locks.",
)
def test_concurrent_duplicate_idempotency_key_creates_one_sale():
    organisation, branch, user, shift, product, _ = create_checkout_context(
        username="concurrent-retry-cashier",
        stock="1.000",
    )
    barrier = threading.Barrier(2)
    key = str(uuid.uuid4())

    def submit():
        close_old_connections()
        client = APIClient()
        client.force_login(user)
        client.defaults["HTTP_X_ORGANISATION_ID"] = str(organisation.pk)
        barrier.wait()
        response = post_checkout(
            client,
            checkout_payload(branch, shift, product, quantity="1.000"),
            key,
        )
        close_old_connections()
        return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(submit)
        second = executor.submit(submit)
        outcomes = [first.result(), second.result()]

    assert sorted(status_code for status_code, _ in outcomes) == [200, 201]
    assert len({body["id"] for _, body in outcomes}) == 1
    assert Sale.objects.for_organisation(organisation).count() == 1
    assert StockMovement.objects.for_organisation(organisation).count() == 1
    assert StockBalance.objects.get(product=product).quantity == Decimal("0.000")


@pytest.mark.django_db
def test_mpesa_payment_is_pending_then_confirmed_and_duplicate_event_is_ignored(
    monkeypatch,
):
    organisation, branch, _, shift, product, client = create_checkout_context(
        username="daraja-cashier",
        extra_permissions=PAYMENT_PERMISSIONS,
    )
    product.selling_price = Decimal("5.00")
    product.tax_rate = Decimal("0.00")
    product.save()
    response = post_checkout(
        client,
        checkout_payload(
            branch,
            shift,
            product,
            payment="mpesa",
        ),
    )
    assert response.status_code == 201
    sale = Sale.objects.get(pk=response.json()["id"])
    payment = Payment.objects.get(sale=sale)
    assert sale.status == Sale.Status.PENDING_PAYMENT
    assert payment.status == Payment.Status.PENDING

    class FakeDarajaClient:
        query_count = 0

        def initiate_stk_push(
            self,
            *,
            amount,
            phone_number,
            account_reference,
            description,
        ):
            assert amount == Decimal("10.00")
            assert phone_number == "254712345678"
            assert account_reference.startswith("BP-")
            assert description == "Retail sale payment"
            return {
                "checkout_request_id": "ws_CO_test_001",
                "merchant_request_id": "merchant_test_001",
            }

        def query_stk_push(self, *, checkout_request_id):
            self.query_count += 1
            assert checkout_request_id == "ws_CO_test_001"
            return {"ResultCode": "0"}

    fake_daraja = FakeDarajaClient()
    monkeypatch.setattr(
        "apps.retail.services.DarajaClient",
        lambda: fake_daraja,
    )
    response = client.post(
        reverse("retail:mpesa-payment-initiate", kwargs={"pk": payment.pk}),
        {"phone_number": "0712345678"},
        format="json",
    )
    assert response.status_code == 202
    payment.refresh_from_db()
    assert payment.checkout_request_id == "ws_CO_test_001"
    assert payment.status == Payment.Status.PENDING

    callback = APIClient()
    callback_payload = {
        "Body": {
            "stkCallback": {
                "CheckoutRequestID": "ws_CO_test_001",
                "ResultCode": 0,
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": 10},
                        {"Name": "MpesaReceiptNumber", "Value": "QAB123XYZ"},
                        {"Name": "PhoneNumber", "Value": 254712345678},
                    ]
                },
            }
        }
    }
    first = callback.post(
        reverse("retail:mpesa-callback"),
        callback_payload,
        format="json",
    )
    duplicate = callback.post(
        reverse("retail:mpesa-callback"),
        callback_payload,
        format="json",
    )

    assert first.status_code == 200
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True
    payment.refresh_from_db()
    sale.refresh_from_db()
    assert payment.status == Payment.Status.CONFIRMED
    assert payment.provider_receipt == "QAB123XYZ"
    assert sale.status == Sale.Status.POSTED
    assert sale.receipt.status == Receipt.Status.ISSUED
    assert sale.receipt.snapshot["payment_status"] == "paid"
    assert sale.receipt.snapshot["payments"][0]["provider_receipt"] == "QAB123XYZ"
    assert PaymentAllocation.objects.filter(payment=payment).count() == 1
    assert MpesaProviderEvent.objects.filter(
        organisation=organisation,
        event_id="ws_CO_test_001",
    ).count() == 1
    assert fake_daraja.query_count == 1


@pytest.mark.django_db
def test_failed_mpesa_payment_voids_sale_and_releases_stock(monkeypatch):
    organisation, branch, _, shift, product, client = create_checkout_context(
        username="failed-mpesa-cashier",
        extra_permissions=PAYMENT_PERMISSIONS,
    )
    product.selling_price = Decimal("5.00")
    product.tax_rate = Decimal("0.00")
    product.save()
    response = post_checkout(
        client,
        checkout_payload(branch, shift, product, payment="mpesa"),
    )
    sale = Sale.objects.get(pk=response.json()["id"])
    payment = Payment.objects.get(sale=sale)

    class FailedDarajaClient:
        def initiate_stk_push(
            self,
            *,
            amount,
            phone_number,
            account_reference,
            description,
        ):
            assert amount == Decimal("10.00")
            assert phone_number == "254712345678"
            assert account_reference.startswith("BP-")
            assert description == "Retail sale payment"
            return {
                "checkout_request_id": "ws_CO_failed_001",
                "merchant_request_id": "merchant_failed_001",
            }

        def query_stk_push(self, *, checkout_request_id):
            assert checkout_request_id == "ws_CO_failed_001"
            return {"ResultCode": "1032"}

    monkeypatch.setattr(
        "apps.retail.services.DarajaClient",
        FailedDarajaClient,
    )
    initiated = client.post(
        reverse("retail:mpesa-payment-initiate", kwargs={"pk": payment.pk}),
        {"phone_number": "0712345678"},
        format="json",
    )
    assert initiated.status_code == 202
    callback = APIClient()
    callback_payload = {
        "Body": {
            "stkCallback": {
                "CheckoutRequestID": "ws_CO_failed_001",
                "ResultCode": 1032,
            }
        }
    }
    failed = callback.post(
        reverse("retail:mpesa-callback"),
        callback_payload,
        format="json",
    )
    duplicate = callback.post(
        reverse("retail:mpesa-callback"),
        callback_payload,
        format="json",
    )

    assert failed.status_code == 200
    assert duplicate.json()["duplicate"] is True
    payment.refresh_from_db()
    sale.refresh_from_db()
    assert payment.status == Payment.Status.FAILED
    assert sale.status == Sale.Status.CANCELLED
    assert sale.cancelled_at is not None
    assert sale.receipt.status == Receipt.Status.VOIDED
    assert sale.receipt.snapshot["payment_status"] == "cancelled"
    assert StockBalance.objects.get(branch=branch, product=product).quantity == (
        Decimal("5.000")
    )
    reversal = StockMovement.objects.get(
        movement_type=StockMovement.MovementType.SALE_REVERSAL,
        sale=sale,
    )
    assert reversal.payment == payment
    assert reversal.quantity_delta == Decimal("2.000")
    assert AuditEvent.objects.filter(
        action="retail.sale.payment_failed_reversed",
        target_id=str(payment.pk),
    ).count() == 1


@pytest.mark.django_db
def test_split_payment_and_credit_sale_limit_and_customer_collection():
    organisation, branch, _, shift, product, client = create_checkout_context(
        username="credit-cashier",
        extra_permissions=PAYMENT_PERMISSIONS,
    )
    product.selling_price = Decimal("5.00")
    product.tax_rate = Decimal("0.00")
    product.save()
    split_response = post_checkout(
        client,
        {
            **checkout_payload(branch, shift, product, payment="split"),
            "payments": [
                {
                    "method": "cash",
                    "amount": "4.00",
                    "amount_tendered": "5.00",
                },
                {"method": "mpesa", "amount": "6.00"},
            ],
        },
    )
    assert split_response.status_code == 201
    split_sale = Sale.objects.get(pk=split_response.json()["id"])
    assert split_sale.status == Sale.Status.PENDING_PAYMENT
    assert split_sale.change_due == Decimal("1.00")
    assert split_sale.payments.count() == 2

    customer = Customer.objects.create(
        organisation=organisation,
        name="Amina Customer",
        phone_number="0712345678",
        credit_limit=Decimal("8.00"),
    )
    credit_payload = {
        "branch": str(branch.pk),
        "shift": str(shift.pk),
        "customer": str(customer.pk),
        "payment_method": "credit",
        "lines": [{"product": str(product.pk), "quantity": "1.000"}],
    }
    credit_response = post_checkout(client, credit_payload)
    assert credit_response.status_code == 201
    credit_sale = Sale.objects.get(pk=credit_response.json()["id"])
    assert credit_sale.credit_amount == Decimal("5.00")
    over_limit_credit = post_checkout(client, credit_payload)
    assert over_limit_credit.status_code == 422
    assert Sale.objects.for_organisation(organisation).filter(
        customer=customer,
        payment_method=Sale.PaymentMethod.CREDIT,
    ).count() == 1

    collection_payload = {
        "branch": str(branch.pk),
        "shift": str(shift.pk),
        "method": "cash",
        "amount": "3.00",
        "allocations": [
            {"sale": str(credit_sale.pk), "amount": "3.00"},
        ],
    }
    collection = client.post(
        reverse(
            "retail:customer-collection",
            kwargs={"customer_pk": customer.pk},
        ),
        collection_payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert collection.status_code == 201
    assert collection.json()["status"] == Payment.Status.CONFIRMED
    assert credit_sale.payment_allocations.aggregate(
        total=Sum("amount")
    )["total"] == Decimal("3.00")
    assert Customer.objects.get(pk=customer.pk).credit_limit == Decimal("8.00")
    from apps.retail.services import customer_credit_balance

    assert customer_credit_balance(
        organisation=organisation,
        customer=customer,
    ) == Decimal("2.00")

    invalid_collection = client.post(
        reverse(
            "retail:customer-collection",
            kwargs={"customer_pk": customer.pk},
        ),
        {
            **collection_payload,
            "amount": "2.01",
            "allocations": [
                {"sale": str(credit_sale.pk), "amount": "2.01"},
            ],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert invalid_collection.status_code == 422


@pytest.mark.django_db
def test_mpesa_sale_return_restocks_and_keeps_refund_pending_until_confirmed(
    monkeypatch,
):
    _, branch, _, shift, product, client = create_checkout_context(
        username="return-cashier",
        extra_permissions=PAYMENT_PERMISSIONS,
    )
    product.selling_price = Decimal("5.00")
    product.tax_rate = Decimal("0.00")
    product.save()
    response = post_checkout(
        client,
        checkout_payload(
            branch,
            shift,
            product,
            payment="mpesa",
        ),
    )
    sale = Sale.objects.get(pk=response.json()["id"])
    payment = Payment.objects.get(sale=sale)

    class ConfirmedDarajaClient:
        def initiate_stk_push(
            self,
            *,
            amount,
            phone_number,
            account_reference,
            description,
        ):
            assert amount == Decimal("10.00")
            assert phone_number == "254712345678"
            assert account_reference.startswith("BP-")
            assert description == "Retail sale payment"
            return {
                "checkout_request_id": "ws_CO_return_001",
                "merchant_request_id": "merchant_return_001",
            }

        def query_stk_push(self, *, checkout_request_id):
            assert checkout_request_id == "ws_CO_return_001"
            return {"ResultCode": "0"}

    monkeypatch.setattr(
        "apps.retail.services.DarajaClient",
        ConfirmedDarajaClient,
    )
    response = client.post(
        reverse("retail:mpesa-payment-initiate", kwargs={"pk": payment.pk}),
        {"phone_number": "0712345678"},
        format="json",
    )
    assert response.status_code == 202
    APIClient().post(
        reverse("retail:mpesa-callback"),
        {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": "ws_CO_return_001",
                    "ResultCode": 0,
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 10},
                            {"Name": "MpesaReceiptNumber", "Value": "QABRETURN"},
                            {"Name": "PhoneNumber", "Value": 254712345678},
                        ]
                    },
                }
            }
        },
        format="json",
    )
    sale.refresh_from_db()
    assert sale.status == Sale.Status.POSTED

    sale_line = SaleLine.objects.get(sale=sale)
    response = client.post(
        reverse("retail:sale-return-create", kwargs={"pk": sale.pk}),
        {
            "reason": "Damaged packaging",
            "refund_method": "mpesa",
            "lines": [
                {"sale_line": str(sale_line.pk), "quantity": "1.000"},
            ],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert response.status_code == 201, response.data
    sale_return = SaleReturn.objects.get(pk=response.json()["id"])
    refund = Refund.objects.get(sale_return=sale_return)
    assert sale_return.total_amount == Decimal("5.00")
    assert refund.status == Refund.Status.PENDING
    assert StockBalance.objects.get(branch=branch, product=product).quantity == Decimal(
        "4.000"
    )
    movement = StockMovement.objects.get(sale_return_line__sale_return=sale_return)
    assert movement.movement_type == StockMovement.MovementType.RETURN
    assert movement.quantity_delta == Decimal("1.000")

    completed = client.post(
        reverse("retail:refund-complete", kwargs={"pk": refund.pk}),
        {"payout_reference": "RFD-12345"},
        format="json",
    )
    assert completed.status_code == 200
    refund.refresh_from_db()
    assert refund.status == Refund.Status.COMPLETED
    assert refund.payout_reference == "RFD-12345"

    excessive_return = client.post(
        reverse("retail:sale-return-create", kwargs={"pk": sale.pk}),
        {
            "reason": "Return remaining",
            "refund_method": "cash",
            "lines": [
                {"sale_line": str(sale_line.pk), "quantity": "2.000"},
            ],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert excessive_return.status_code == 422


@pytest.mark.django_db
def test_cross_tenant_customer_collection_and_sale_return_are_denied():
    organisation, branch, _, shift, product, _ = create_checkout_context(
        username="payment-tenant-one",
        extra_permissions=PAYMENT_PERMISSIONS,
    )
    customer = Customer.objects.create(
        organisation=organisation,
        name="Tenant One Customer",
        credit_limit=Decimal("100.00"),
    )
    sale_response = post_checkout(
        _,
        {
            "branch": str(branch.pk),
            "shift": str(shift.pk),
            "customer": str(customer.pk),
            "payment_method": "credit",
            "lines": [{"product": str(product.pk), "quantity": "1.000"}],
        },
    )
    sale_id = sale_response.json()["id"]

    foreign_org = create_organisation("Payment foreign tenant")
    foreign_branch = Branch.objects.create(
        organisation=foreign_org,
        name="Foreign branch",
    )
    foreign_user = create_user("payment-tenant-two")
    grant_retail_access(
        foreign_user,
        foreign_org,
        foreign_branch,
        [CHECKOUT_PERMISSION, SALES_VIEW_PERMISSION, *PAYMENT_PERMISSIONS],
    )
    foreign_client = APIClient()
    foreign_client.force_login(foreign_user)
    foreign_client.defaults["HTTP_X_ORGANISATION_ID"] = str(foreign_org.pk)
    collection = foreign_client.post(
        reverse(
            "retail:customer-collection",
            kwargs={"customer_pk": customer.pk},
        ),
        {
            "branch": str(foreign_branch.pk),
            "shift": str(
                Shift.objects.create(
                    organisation=foreign_org,
                    branch=foreign_branch,
                    cashier=foreign_user,
                    opening_float=Decimal("0.00"),
                ).pk
            ),
            "method": "cash",
            "amount": "1.00",
            "allocations": [
                {"sale": sale_id, "amount": "1.00"},
            ],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert collection.status_code == 404
    foreign_return = foreign_client.post(
        reverse("retail:sale-return-create", kwargs={"pk": sale_id}),
        {
            "reason": "Cross-tenant attempt",
            "refund_method": "cash",
            "lines": [{"sale_line": str(SaleLine.objects.get(sale_id=sale_id).pk),
                       "quantity": "1.000"}],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert foreign_return.status_code == 404
