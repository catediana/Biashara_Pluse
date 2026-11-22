import hashlib
import json
import uuid
from decimal import Decimal

from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.integrations.mpesa import (
    DarajaClient,
    MpesaProviderError,
    normalize_kenyan_phone,
)
from apps.retail.models import (
    Customer,
    GoodsReceipt,
    GoodsReceiptLine,
    MpesaProviderEvent,
    Payment,
    PaymentAllocation,
    Product,
    Refund,
    Receipt,
    Sale,
    SaleLine,
    SaleReturn,
    SaleReturnLine,
    Shift,
    StockAdjustment,
    StockBalance,
    StockMovement,
)
from core.exceptions import BusinessRuleError, ConflictError
from core.money import quantize_money


def _decimal_text(value):
    return format(value, "f")


def _fingerprint(payload):
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def goods_receipt_fingerprint(data):
    lines = sorted(data["lines"], key=lambda line: str(line["product"].pk))
    return _fingerprint(
        {
            "branch": str(data["branch"].pk),
            "supplier": str(data["supplier"].pk),
            "supplier_reference": data.get("supplier_reference", ""),
            "lines": [
                {
                    "product": str(line["product"].pk),
                    "quantity": _decimal_text(line["quantity"]),
                    "unit_cost": _decimal_text(line["unit_cost"]),
                }
                for line in lines
            ],
        }
    )


def stock_adjustment_fingerprint(data):
    return _fingerprint(
        {
            "branch": str(data["branch"].pk),
            "product": str(data["product"].pk),
            "quantity_delta": _decimal_text(data["quantity_delta"]),
            "expected_stock_version": data["expected_stock_version"],
            "reason": data["reason"],
        }
    )


def checkout_fingerprint(data):
    lines = sorted(data["lines"], key=lambda line: str(line["product"].pk))
    payments = sorted(
        data.get("payments", []),
        key=lambda payment: (
            payment["method"],
            _decimal_text(payment["amount"]),
        ),
    )
    return _fingerprint(
        {
            "branch": str(data["branch"].pk),
            "shift": str(data["shift"].pk),
            "payment_method": data["payment_method"],
            "customer": str(data["customer"].pk) if data.get("customer") else None,
            "amount_tendered": (
                _decimal_text(data["amount_tendered"])
                if data.get("amount_tendered") is not None
                else None
            ),
            "payments": [
                {
                    "method": payment["method"],
                    "amount": _decimal_text(payment["amount"]),
                    "amount_tendered": (
                        _decimal_text(payment["amount_tendered"])
                        if payment.get("amount_tendered") is not None
                        else None
                    ),
                    "phone_number": payment.get("phone_number", ""),
                }
                for payment in payments
            ],
            "lines": [
                {
                    "product": str(line["product"].pk),
                    "quantity": _decimal_text(line["quantity"]),
                }
                for line in lines
            ],
        }
    )


def collection_fingerprint(data):
    allocations = sorted(
        data["allocations"],
        key=lambda item: str(item["sale"].pk),
    )
    return _fingerprint(
        {
            "branch": str(data["branch"].pk),
            "shift": str(data["shift"].pk),
            "method": data["method"],
            "amount": _decimal_text(data["amount"]),
            "phone_number": data.get("phone_number", ""),
            "allocations": [
                {
                    "sale": str(item["sale"].pk),
                    "amount": _decimal_text(item["amount"]),
                }
                for item in allocations
            ],
        }
    )


def return_fingerprint(data, *, sale_id):
    lines = sorted(
        data["lines"],
        key=lambda item: str(item["sale_line"].pk),
    )
    return _fingerprint(
        {
            "sale": str(sale_id),
            "reason": data["reason"],
            "refund_method": data.get("refund_method", ""),
            "lines": [
                {
                    "sale_line": str(item["sale_line"].pk),
                    "quantity": _decimal_text(item["quantity"]),
                }
                for item in lines
            ],
        }
    )


def _sale_totals(lines):
    calculated_lines = []
    subtotal = Decimal("0.00")
    tax_total = Decimal("0.00")
    for line in lines:
        product = line["product"]
        quantity = line["quantity"]
        line_subtotal = quantize_money(quantity * product.selling_price)
        tax_amount = quantize_money(
            line_subtotal * product.tax_rate / Decimal("100")
        )
        line_total = line_subtotal + tax_amount
        calculated_lines.append(
            {
                "product": product,
                "quantity": quantity,
                "product_name": product.name,
                "sku": product.sku,
                "unit": product.unit,
                "unit_price": product.selling_price,
                "unit_cost": product.cost_price,
                "tax_rate": product.tax_rate,
                "line_subtotal": line_subtotal,
                "tax_amount": tax_amount,
                "line_total": line_total,
            }
        )
        subtotal += line_subtotal
        tax_total += tax_amount
    return calculated_lines, quantize_money(subtotal), quantize_money(tax_total)


def build_receipt_snapshot(sale):
    if sale.status == Sale.Status.PENDING_PAYMENT:
        payment_status = "pending_payment"
    elif sale.status == Sale.Status.CANCELLED:
        payment_status = "cancelled"
    elif sale.payment_method == Sale.PaymentMethod.CREDIT:
        payment_status = "credit"
    else:
        payment_status = "paid"
    return {
        "receipt_number": sale.sale_number,
        "sale_id": str(sale.pk),
        "organisation": sale.organisation.name,
        "branch": sale.branch.name,
        "date": sale.created_at.isoformat(),
        "cashier": sale.cashier.get_full_name() or sale.cashier.get_username(),
        "payment_method": sale.payment_method,
        "payment_status": payment_status,
        "customer": str(sale.customer_id) if sale.customer_id else None,
        "currency": sale.organisation.currency,
        "lines": [
            {
                "product_name": line.product_name,
                "sku": line.sku,
                "unit": line.unit,
                "quantity": format(line.quantity, "f"),
                "unit_price": format(line.unit_price, ".2f"),
                "tax_rate": format(line.tax_rate, ".2f"),
                "tax_amount": format(line.tax_amount, ".2f"),
                "line_total": format(line.line_total, ".2f"),
            }
            for line in sale.lines.all()
        ],
        "subtotal": format(sale.subtotal, ".2f"),
        "tax_total": format(sale.tax_total, ".2f"),
        "total": format(sale.total, ".2f"),
        "amount_tendered": (
            format(sale.amount_tendered, ".2f")
            if sale.amount_tendered is not None
            else None
        ),
        "change_due": format(sale.change_due, ".2f"),
        "payments": [
            {
                "method": payment.method,
                "amount": format(payment.amount, ".2f"),
                "status": payment.status,
                "provider_receipt": payment.provider_receipt or None,
            }
            for payment in sale.payments.order_by("created_at")
        ],
    }


def _check_retry(existing, fingerprint):
    if existing.request_fingerprint != fingerprint:
        raise ConflictError(
            "This idempotency key was already used for a different request."
        )
    return existing, False


def customer_credit_balance(*, organisation, customer):
    credit_sales = Sale.objects.for_organisation(organisation).filter(
        customer=customer,
        payment_method=Sale.PaymentMethod.CREDIT,
    )
    credit_total = credit_sales.aggregate(total=Sum("credit_amount"))["total"]
    collected = PaymentAllocation.objects.for_organisation(organisation).filter(
        sale__in=credit_sales,
        payment__purpose=Payment.Purpose.COLLECTION,
        payment__status=Payment.Status.CONFIRMED,
    ).aggregate(total=Sum("amount"))["total"]
    credit_returns = SaleReturn.objects.for_organisation(organisation).filter(
        sale__in=credit_sales
    ).aggregate(total=Sum("credit_reduction_amount"))["total"]
    return max(
        (credit_total or Decimal("0.00"))
        - (collected or Decimal("0.00"))
        - (credit_returns or Decimal("0.00")),
        Decimal("0.00"),
    )


def checkout(
    *,
    organisation,
    branch,
    shift,
    lines,
    payment_method,
    amount_tendered,
    customer,
    payment_parts,
    idempotency_key,
    request_fingerprint,
    actor,
):
    try:
        with transaction.atomic():
            existing = (
                Sale.objects.for_organisation(organisation)
                .select_for_update()
                .filter(idempotency_key=idempotency_key)
                .first()
            )
            if existing is not None:
                return _check_retry(existing, request_fingerprint)

            locked_customer = None
            if customer is not None:
                locked_customer = (
                    Customer.objects.for_organisation(organisation)
                    .select_for_update()
                    .filter(pk=customer.pk, is_active=True)
                    .first()
                )
                if locked_customer is None:
                    raise BusinessRuleError(
                        "The selected customer is no longer active."
                    )

            locked_shift = (
                Shift.objects.for_organisation(organisation)
                .select_for_update()
                .filter(
                    pk=shift.pk,
                    branch=branch,
                    cashier=actor,
                    status=Shift.Status.OPEN,
                )
                .first()
            )
            if locked_shift is None:
                raise BusinessRuleError(
                    "Checkout requires the cashier's open shift at this branch."
                )

            existing = (
                Sale.objects.for_organisation(organisation)
                .select_for_update()
                .filter(idempotency_key=idempotency_key)
                .first()
            )
            if existing is not None:
                return _check_retry(existing, request_fingerprint)

            product_ids = sorted(
                (line["product"].pk for line in lines),
                key=str,
            )
            products = list(
                Product.objects.for_organisation(organisation)
                .select_for_update()
                .filter(pk__in=product_ids, is_active=True)
                .order_by("pk")
            )
            if len(products) != len(product_ids):
                raise BusinessRuleError(
                    "One or more products are no longer available."
                )
            products_by_id = {product.pk: product for product in products}
            current_lines = [
                {
                    "product": products_by_id[line["product"].pk],
                    "quantity": line["quantity"],
                }
                for line in lines
            ]

            balances = list(
                StockBalance.objects.for_organisation(organisation)
                .select_for_update()
                .filter(branch=branch, product_id__in=product_ids)
                .order_by("product_id")
            )
            balances_by_product = {balance.product_id: balance for balance in balances}
            for line in current_lines:
                product = line["product"]
                balance = balances_by_product.get(product.pk)
                if (
                    balance is None
                    or balance.quantity < line["quantity"]
                ):
                    raise BusinessRuleError(
                        f"Insufficient stock for product {product.sku}."
                    )

            calculated_lines, subtotal, tax_total = _sale_totals(current_lines)
            total = subtotal + tax_total
            if payment_method == Sale.PaymentMethod.CASH:
                tendered = amount_tendered if amount_tendered is not None else total
                if tendered < total:
                    raise BusinessRuleError(
                        "Cash tendered must cover the sale total."
                    )
                change_due = tendered - total
                sale_status = Sale.Status.POSTED
                completed_at = timezone.now()
                resolved_payment_parts = [
                    {
                        "method": Payment.Method.CASH,
                        "amount": total,
                        "amount_tendered": tendered,
                        "phone_number": "",
                    }
                ]
            elif payment_method == Sale.PaymentMethod.MPESA:
                if total != total.to_integral_value():
                    raise BusinessRuleError(
                        "M-Pesa amounts must be whole currency units."
                    )
                tendered = None
                change_due = Decimal("0.00")
                sale_status = Sale.Status.PENDING_PAYMENT
                completed_at = None
                resolved_payment_parts = [
                    {
                        "method": Payment.Method.MPESA,
                        "amount": total,
                        "amount_tendered": None,
                        "phone_number": "",
                    }
                ]
            elif payment_method == Sale.PaymentMethod.SPLIT:
                resolved_payment_parts = payment_parts
                if sum(
                    (part["amount"] for part in resolved_payment_parts),
                    Decimal("0.00"),
                ) != total:
                    raise BusinessRuleError(
                        "Split payment allocations must equal the sale total."
                    )
                tendered = sum(
                    (
                        part["amount_tendered"]
                        for part in resolved_payment_parts
                        if part["method"] == Payment.Method.CASH
                    ),
                    Decimal("0.00"),
                )
                cash_amount = sum(
                    (
                        part["amount"]
                        for part in resolved_payment_parts
                        if part["method"] == Payment.Method.CASH
                    ),
                    Decimal("0.00"),
                )
                change_due = tendered - cash_amount
                has_pending_mpesa = any(
                    part["method"] == Payment.Method.MPESA
                    for part in resolved_payment_parts
                )
                sale_status = (
                    Sale.Status.PENDING_PAYMENT
                    if has_pending_mpesa
                    else Sale.Status.POSTED
                )
                completed_at = None if has_pending_mpesa else timezone.now()
            elif payment_method == Sale.PaymentMethod.CREDIT:
                if locked_customer is None:
                    raise BusinessRuleError(
                        "A customer is required for a credit sale."
                    )
                outstanding = customer_credit_balance(
                    organisation=organisation,
                    customer=locked_customer,
                )
                if outstanding + total > locked_customer.credit_limit:
                    raise BusinessRuleError(
                        "The sale exceeds the customer's available credit limit."
                    )
                resolved_payment_parts = []
                tendered = None
                change_due = Decimal("0.00")
                sale_status = Sale.Status.POSTED
                completed_at = timezone.now()
            else:
                raise BusinessRuleError("Unsupported payment method.")

            sale_id = uuid.uuid4()
            sale_number = f"BP-{sale_id.hex.upper()}"
            sale = Sale.objects.create(
                id=sale_id,
                organisation=organisation,
                branch=branch,
                shift=locked_shift,
                cashier=actor,
                customer=locked_customer,
                sale_number=sale_number,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                payment_method=payment_method,
                status=sale_status,
                subtotal=subtotal,
                tax_total=tax_total,
                total=total,
                credit_amount=(
                    total
                    if payment_method == Sale.PaymentMethod.CREDIT
                    else Decimal("0.00")
                ),
                amount_tendered=tendered,
                change_due=change_due,
                completed_at=completed_at,
            )

            for index, part in enumerate(resolved_payment_parts):
                phone_number = part.get("phone_number", "")
                if phone_number:
                    try:
                        phone_number = normalize_kenyan_phone(phone_number)
                    except ValueError as exc:
                        raise BusinessRuleError(str(exc)) from exc
                payment_status = (
                    Payment.Status.CONFIRMED
                    if part["method"] == Payment.Method.CASH
                    else Payment.Status.PENDING
                )
                payment_key = uuid.uuid5(
                    idempotency_key,
                    f"{index}:{part['method']}",
                )
                payment = Payment.objects.create(
                    organisation=organisation,
                    purpose=Payment.Purpose.SALE,
                    method=part["method"],
                    status=payment_status,
                    sale=sale,
                    customer=locked_customer,
                    branch=branch,
                    shift=locked_shift,
                    amount=part["amount"],
                    idempotency_key=payment_key,
                    request_fingerprint=_fingerprint(
                        {
                            "sale": str(sale.pk),
                            "method": part["method"],
                            "amount": _decimal_text(part["amount"]),
                        }
                    ),
                    phone_number=phone_number,
                    initiated_by=actor,
                    confirmed_at=(
                        timezone.now()
                        if payment_status == Payment.Status.CONFIRMED
                        else None
                    ),
                )
                PaymentAllocation.objects.create(
                    organisation=organisation,
                    payment=payment,
                    sale=sale,
                    amount=part["amount"],
                )

            for line in calculated_lines:
                product = line["product"]
                quantity = line["quantity"]
                SaleLine.objects.create(
                    organisation=organisation,
                    sale=sale,
                    **line,
                )
                balance = balances_by_product[product.pk]
                balance.quantity -= quantity
                balance.version += 1
                balance.save(
                    update_fields=["quantity", "version", "updated_at"]
                )
                StockMovement.objects.create(
                    organisation=organisation,
                    branch=branch,
                    product=product,
                    movement_type=StockMovement.MovementType.SALE,
                    quantity_delta=-quantity,
                    unit_cost=line["unit_cost"],
                    sale=sale,
                    created_by=actor,
                )

            receipt_status = (
                Receipt.Status.ISSUED
                if sale.status == Sale.Status.POSTED
                else Receipt.Status.PENDING_PAYMENT
            )
            Receipt.objects.create(
                organisation=organisation,
                sale=sale,
                receipt_number=sale.sale_number,
                status=receipt_status,
                snapshot=build_receipt_snapshot(sale),
            )
            AuditEvent.objects.create(
                organisation=organisation,
                actor=actor,
                action="retail.sale.checkout",
                target_type="retail.Sale",
                target_id=str(sale.pk),
                correlation_id=idempotency_key,
                metadata={
                    "sale_number": sale.sale_number,
                    "branch_id": str(branch.pk),
                    "shift_id": str(locked_shift.pk),
                    "payment_method": payment_method,
                    "customer_id": str(locked_customer.pk)
                    if locked_customer
                    else None,
                    "status": sale.status,
                    "total": format(total, ".2f"),
                    "currency": organisation.currency,
                },
            )
            return sale, True
    except IntegrityError:
        existing_result = _find_existing(
            Sale,
            organisation,
            idempotency_key,
            request_fingerprint,
        )
        if existing_result is None:
            raise
        return existing_result


def start_mpesa_payment(
    *,
    organisation,
    payment_id,
    phone_number,
    actor,
    client=None,
):
    try:
        normalized_phone = normalize_kenyan_phone(phone_number)
    except ValueError as exc:
        raise BusinessRuleError(str(exc)) from exc

    with transaction.atomic():
        payment = (
            Payment.objects.for_organisation(organisation)
            .select_for_update()
            .select_related("shift")
            .filter(pk=payment_id)
            .first()
        )
        if payment is None:
            return None, False
        if payment.method != Payment.Method.MPESA:
            raise BusinessRuleError("Only M-Pesa payments can start an STK Push.")
        if payment.amount != payment.amount.to_integral_value():
            raise BusinessRuleError(
                "M-Pesa amounts must be whole currency units."
            )
        if payment.status != Payment.Status.PENDING:
            raise ConflictError("Only pending M-Pesa payments can be initiated.")
        if payment.shift_id and payment.shift.status != Shift.Status.OPEN:
            raise BusinessRuleError(
                "A closed shift cannot accept a new M-Pesa payment."
            )
        if (
            payment.phone_number
            and payment.phone_number != normalized_phone
        ):
            raise ConflictError(
                "The M-Pesa phone number cannot change after payment creation."
            )
        if payment.checkout_request_id:
            if payment.phone_number != normalized_phone:
                raise ConflictError(
                    "This payment already has an STK Push for a different phone."
                )
            return payment, False
        if payment.initiation_started_at is not None:
            raise ConflictError(
                "The STK Push outcome is unresolved; do not initiate it again."
            )
        if client is None:
            try:
                client = DarajaClient()
            except ImproperlyConfigured as exc:
                raise MpesaProviderError(
                    "Daraja payment configuration is incomplete."
                ) from exc
        payment.phone_number = normalized_phone
        payment.initiation_started_at = timezone.now()
        payment.save(update_fields=["phone_number", "initiation_started_at", "updated_at"])
        account_reference = (
            payment.sale.sale_number
            if payment.sale_id
            else f"COL-{payment.pk.hex[:12].upper()}"
        )
        description = (
            "Retail sale payment"
            if payment.purpose == Payment.Purpose.SALE
            else "Customer collection"
        )
        amount = payment.amount

    result = client.initiate_stk_push(
        amount=amount,
        phone_number=normalized_phone,
        account_reference=account_reference,
        description=description,
    )
    with transaction.atomic():
        payment = (
            Payment.objects.for_organisation(organisation)
            .select_for_update()
            .get(pk=payment_id)
        )
        payment.checkout_request_id = result["checkout_request_id"]
        payment.merchant_request_id = result["merchant_request_id"]
        payment.save(
            update_fields=[
                "checkout_request_id",
                "merchant_request_id",
                "updated_at",
            ]
        )
        AuditEvent.objects.create(
            organisation=organisation,
            actor=actor,
            action="retail.payment.mpesa.initiated",
            target_type="retail.Payment",
            target_id=str(payment.pk),
            correlation_id=payment.idempotency_key,
            metadata={
                "payment_id": str(payment.pk),
                "purpose": payment.purpose,
                "amount": format(payment.amount, ".2f"),
                "currency": organisation.currency,
            },
        )
    return payment, True


def _callback_metadata(callback):
    values = {}
    metadata = callback.get("CallbackMetadata", {}).get("Item", [])
    for item in metadata:
        if isinstance(item, dict) and item.get("Name"):
            values[item["Name"]] = item.get("Value")
    return values


def _reverse_failed_mpesa_sale(*, organisation, payment):
    sale = (
        Sale.objects.for_organisation(organisation)
        .select_for_update()
        .get(pk=payment.sale_id)
    )
    if (
        sale.payment_method != Sale.PaymentMethod.MPESA
        or sale.status != Sale.Status.PENDING_PAYMENT
    ):
        return False

    sale_lines = list(
        SaleLine.objects.for_organisation(organisation)
        .filter(sale=sale)
        .order_by("product_id")
    )
    product_ids = [line.product_id for line in sale_lines]
    balances = list(
        StockBalance.objects.for_organisation(organisation)
        .select_for_update()
        .filter(branch=sale.branch, product_id__in=product_ids)
        .order_by("product_id")
    )
    balances_by_product = {balance.product_id: balance for balance in balances}
    sale.status = Sale.Status.CANCELLED
    sale.cancelled_at = timezone.now()
    sale.save(update_fields=["status", "cancelled_at", "updated_at"])
    for line in sale_lines:
        balance = balances_by_product.get(line.product_id)
        if balance is None:
            balance = StockBalance.objects.create(
                organisation=organisation,
                branch=sale.branch,
                product_id=line.product_id,
                quantity=Decimal("0.000"),
                average_cost=line.unit_cost,
            )
            balances_by_product[line.product_id] = balance
        balance.quantity += line.quantity
        balance.version += 1
        balance.save(update_fields=["quantity", "version", "updated_at"])
        StockMovement.objects.create(
            organisation=organisation,
            branch=sale.branch,
            product_id=line.product_id,
            movement_type=StockMovement.MovementType.SALE_REVERSAL,
            quantity_delta=line.quantity,
            unit_cost=line.unit_cost,
            sale=sale,
            payment=payment,
            created_by=payment.initiated_by,
        )

    receipt = sale.receipt
    if receipt.status == Receipt.Status.PENDING_PAYMENT:
        receipt.status = Receipt.Status.VOIDED
        receipt.snapshot = build_receipt_snapshot(sale)
        receipt.save(update_fields=["status", "snapshot"])
    return True


def process_mpesa_callback(payload, *, client=None):
    try:
        callback = payload["Body"]["stkCallback"]
        checkout_request_id = callback["CheckoutRequestID"]
        callback_code = str(callback["ResultCode"])
    except (KeyError, TypeError) as exc:
        raise BusinessRuleError("Invalid Daraja callback payload.") from exc

    payment = (
        Payment.objects.filter(
            method=Payment.Method.MPESA,
            checkout_request_id=checkout_request_id,
        )
        .select_related("organisation", "sale", "customer")
        .first()
    )
    if payment is None:
        raise ConflictError("No matching pending M-Pesa payment was found.")

    metadata = _callback_metadata(callback)
    callback_merchant_id = str(callback.get("MerchantRequestID", ""))
    event_fingerprint = _fingerprint(
        {
            "result_code": callback_code,
            "merchant_request_id": callback_merchant_id,
            "amount": str(metadata.get("Amount", "")),
            "receipt": str(metadata.get("MpesaReceiptNumber", "")),
            "phone": str(metadata.get("PhoneNumber", "")),
        }
    )
    with transaction.atomic():
        payment = (
            Payment.objects.for_organisation(payment.organisation)
            .select_for_update()
            .get(pk=payment.pk)
        )
        event = (
            MpesaProviderEvent.objects.for_organisation(payment.organisation)
            .select_for_update()
            .filter(event_id=checkout_request_id)
            .first()
        )
        if event is not None:
            if event.payload_fingerprint != event_fingerprint:
                raise ConflictError(
                    "A different callback was already received for this provider request."
                )
            if event.status in (
                MpesaProviderEvent.Status.PROCESSED,
                MpesaProviderEvent.Status.REJECTED,
            ):
                return payment, False
        if client is None:
            try:
                client = DarajaClient()
            except ImproperlyConfigured as exc:
                raise MpesaProviderError(
                    "Daraja payment configuration is incomplete."
                ) from exc
        if event is None:
            event = MpesaProviderEvent.objects.create(
                organisation=payment.organisation,
                event_id=checkout_request_id,
                payment=payment,
                result_code=callback_code,
                payload_fingerprint=event_fingerprint,
            )

    provider_result = client.query_stk_push(
        checkout_request_id=checkout_request_id,
    )
    provider_code = provider_result.get("ResultCode")
    if provider_code is None:
        raise MpesaProviderError(
            "Daraja has not confirmed the payment outcome; the payment remains pending."
        )
    provider_code = str(provider_code)

    provider_outcome_matches = callback_code == provider_code and (
        not callback_merchant_id
        or callback_merchant_id == payment.merchant_request_id
    )
    success = provider_outcome_matches and provider_code == "0"
    callback_amount = metadata.get("Amount")
    callback_receipt = str(metadata.get("MpesaReceiptNumber", "")).strip()
    callback_phone = metadata.get("PhoneNumber")
    if success:
        try:
            amount_matches = Decimal(str(callback_amount)) == payment.amount
            phone_matches = (
                normalize_kenyan_phone(str(callback_phone))
                == payment.phone_number
            )
        except (ValueError, TypeError):
            amount_matches = False
            phone_matches = False
        success = amount_matches and phone_matches and bool(callback_receipt)
    valid_outcome = provider_outcome_matches and (
        provider_code != "0" or success
    )

    with transaction.atomic():
        payment = (
            Payment.objects.for_organisation(payment.organisation)
            .select_for_update()
            .get(pk=payment.pk)
        )
        event = (
            MpesaProviderEvent.objects.for_organisation(payment.organisation)
            .select_for_update()
            .get(pk=event.pk)
        )
        sale_reversed = False
        if payment.status == Payment.Status.PENDING and valid_outcome:
            if success:
                payment.status = Payment.Status.CONFIRMED
                payment.confirmed_at = timezone.now()
                payment.provider_receipt = callback_receipt
                payment.save(
                    update_fields=[
                        "status",
                        "confirmed_at",
                        "provider_receipt",
                        "updated_at",
                    ]
                )
                if payment.sale_id:
                    sale = (
                        Sale.objects.for_organisation(payment.organisation)
                        .select_for_update()
                        .get(pk=payment.sale_id)
                    )
                    pending_count = sale.payments.filter(
                        status=Payment.Status.PENDING
                    ).count()
                    failed_count = sale.payments.filter(
                        status=Payment.Status.FAILED
                    ).count()
                    if (
                        sale.status == Sale.Status.PENDING_PAYMENT
                        and pending_count == 0
                        and failed_count == 0
                    ):
                        sale.status = Sale.Status.POSTED
                        sale.completed_at = timezone.now()
                        sale.save(
                            update_fields=["status", "completed_at", "updated_at"]
                        )
                        receipt = sale.receipt
                        if receipt.status == Receipt.Status.PENDING_PAYMENT:
                            receipt.status = Receipt.Status.ISSUED
                            receipt.snapshot = build_receipt_snapshot(sale)
                            receipt.save(update_fields=["status", "snapshot"])
            else:
                payment.status = Payment.Status.FAILED
                payment.save(update_fields=["status", "updated_at"])
                if payment.sale_id:
                    sale_reversed = _reverse_failed_mpesa_sale(
                        organisation=payment.organisation,
                        payment=payment,
                    )

        event.status = (
            MpesaProviderEvent.Status.PROCESSED
            if valid_outcome
            else MpesaProviderEvent.Status.REJECTED
        )
        event.processed_at = timezone.now()
        event.save(update_fields=["status", "processed_at"])
        AuditEvent.objects.create(
            organisation=payment.organisation,
            actor=None,
            action=(
                "retail.payment.mpesa.confirmed"
                if success
                else (
                    (
                        "retail.sale.payment_failed_reversed"
                        if sale_reversed
                        else "retail.payment.mpesa.failed"
                    )
                    if valid_outcome
                    else "retail.payment.mpesa.callback_rejected"
                )
            ),
            target_type="retail.Payment",
            target_id=str(payment.pk),
            correlation_id=payment.idempotency_key,
            metadata={
                "payment_id": str(payment.pk),
                "result_code": provider_code,
                "provider_receipt": callback_receipt if success else "",
                "sale_reversed": sale_reversed,
            },
        )
    return payment, True


def _sale_credit_due(*, organisation, sale):
    collected = PaymentAllocation.objects.for_organisation(organisation).filter(
        sale=sale,
        payment__purpose=Payment.Purpose.COLLECTION,
        payment__status__in=[Payment.Status.CONFIRMED, Payment.Status.PENDING],
    ).aggregate(total=Sum("amount"))["total"]
    returned = SaleReturn.objects.for_organisation(organisation).filter(
        sale=sale
    ).aggregate(total=Sum("credit_reduction_amount"))["total"]
    return max(
        sale.credit_amount
        - (collected or Decimal("0.00"))
        - (returned or Decimal("0.00")),
        Decimal("0.00"),
    )


def record_customer_collection(
    *,
    organisation,
    customer,
    branch,
    shift,
    method,
    amount,
    allocations,
    phone_number,
    idempotency_key,
    request_fingerprint,
    actor,
):
    if method == Payment.Method.MPESA:
        if amount != amount.to_integral_value():
            raise BusinessRuleError(
                "M-Pesa amounts must be whole currency units."
            )
        try:
            phone_number = normalize_kenyan_phone(phone_number)
        except ValueError as exc:
            raise BusinessRuleError(str(exc)) from exc

    try:
        with transaction.atomic():
            existing = (
                Payment.objects.for_organisation(organisation)
                .select_for_update()
                .filter(idempotency_key=idempotency_key)
                .first()
            )
            if existing is not None:
                return _check_retry(existing, request_fingerprint)

            locked_customer = (
                Customer.objects.for_organisation(organisation)
                .select_for_update()
                .filter(pk=customer.pk, is_active=True)
                .first()
            )
            if locked_customer is None:
                raise BusinessRuleError("The selected customer is not active.")
            locked_shift = (
                Shift.objects.for_organisation(organisation)
                .select_for_update()
                .filter(
                    pk=shift.pk,
                    branch=branch,
                    cashier=actor,
                    status=Shift.Status.OPEN,
                )
                .first()
            )
            if locked_shift is None:
                raise BusinessRuleError(
                    "A customer collection requires the cashier's open shift."
                )
            if not allocations or sum(
                (item["amount"] for item in allocations), Decimal("0.00")
            ) != amount:
                raise BusinessRuleError(
                    "Collection allocations must equal the payment amount."
                )
            sale_ids = sorted(
                (item["sale"].pk for item in allocations),
                key=str,
            )
            sales = list(
                Sale.objects.for_organisation(organisation)
                .select_for_update()
                .filter(
                    pk__in=sale_ids,
                    customer=locked_customer,
                    payment_method=Sale.PaymentMethod.CREDIT,
                    status=Sale.Status.POSTED,
                )
                .order_by("pk")
            )
            if len(sales) != len(sale_ids):
                raise BusinessRuleError(
                    "Collections can only be allocated to this customer's credit sales."
                )
            sales_by_id = {sale.pk: sale for sale in sales}
            requested_by_sale = {}
            for item in allocations:
                sale = sales_by_id[item["sale"].pk]
                if item["amount"] <= 0:
                    raise BusinessRuleError(
                        "Collection allocation amounts must be positive."
                    )
                requested_by_sale[sale.pk] = (
                    requested_by_sale.get(sale.pk, Decimal("0.00"))
                    + item["amount"]
                )
            for sale_id, allocation_amount in requested_by_sale.items():
                if allocation_amount > _sale_credit_due(
                    organisation=organisation,
                    sale=sales_by_id[sale_id],
                ):
                    raise BusinessRuleError(
                        "Collection allocation exceeds the sale's outstanding balance."
                    )

            payment = Payment.objects.create(
                organisation=organisation,
                purpose=Payment.Purpose.COLLECTION,
                method=method,
                status=(
                    Payment.Status.CONFIRMED
                    if method == Payment.Method.CASH
                    else Payment.Status.PENDING
                ),
                customer=locked_customer,
                branch=branch,
                shift=locked_shift,
                amount=amount,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                phone_number=phone_number or "",
                initiated_by=actor,
                confirmed_at=(
                    timezone.now() if method == Payment.Method.CASH else None
                ),
            )
            for sale_id, allocation_amount in requested_by_sale.items():
                PaymentAllocation.objects.create(
                    organisation=organisation,
                    payment=payment,
                    sale=sales_by_id[sale_id],
                    amount=allocation_amount,
                )
            AuditEvent.objects.create(
                organisation=organisation,
                actor=actor,
                action="retail.customer.collection.recorded",
                target_type="retail.Payment",
                target_id=str(payment.pk),
                correlation_id=idempotency_key,
                metadata={
                    "customer_id": str(locked_customer.pk),
                    "amount": format(amount, ".2f"),
                    "method": method,
                    "status": payment.status,
                    "sale_ids": [str(sale_id) for sale_id in requested_by_sale],
                },
            )
            return payment, True
    except IntegrityError:
        existing_result = _find_existing(
            Payment,
            organisation,
            idempotency_key,
            request_fingerprint,
        )
        if existing_result is None:
            raise
        return existing_result


def return_sale(
    *,
    organisation,
    sale_id,
    lines,
    reason,
    refund_method,
    idempotency_key,
    request_fingerprint,
    actor,
):
    try:
        with transaction.atomic():
            existing = (
                SaleReturn.objects.for_organisation(organisation)
                .select_for_update()
                .filter(idempotency_key=idempotency_key)
                .first()
            )
            if existing is not None:
                return _check_retry(existing, request_fingerprint)

            initial_sale = (
                Sale.objects.for_organisation(organisation)
                .filter(pk=sale_id)
                .select_related("customer")
                .first()
            )
            if initial_sale is None:
                return None, False
            if initial_sale.customer_id:
                Customer.objects.for_organisation(organisation).select_for_update().get(
                    pk=initial_sale.customer_id
                )
            sale = (
                Sale.objects.for_organisation(organisation)
                .select_for_update()
                .select_related("customer", "branch")
                .get(pk=sale_id)
            )
            if sale.status != Sale.Status.POSTED:
                raise BusinessRuleError(
                    "Only completed sales can be returned."
                )
            if PaymentAllocation.objects.for_organisation(organisation).filter(
                sale=sale,
                payment__purpose=Payment.Purpose.COLLECTION,
                payment__status=Payment.Status.PENDING,
            ).exists():
                raise ConflictError(
                    "Resolve pending customer collections before returning this sale."
                )
            sale_lines = list(
                SaleLine.objects.for_organisation(organisation)
                .select_for_update()
                .filter(sale=sale, pk__in=[item["sale_line"].pk for item in lines])
                .order_by("pk")
            )
            if len(sale_lines) != len(lines):
                raise BusinessRuleError(
                    "Return lines must belong to the selected sale."
                )

            line_data = []
            total_amount = Decimal("0.00")
            for requested in lines:
                sale_line = next(
                    line
                    for line in sale_lines
                    if line.pk == requested["sale_line"].pk
                )
                quantity = requested["quantity"]
                previous = SaleReturnLine.objects.for_organisation(
                    organisation
                ).filter(sale_line=sale_line).aggregate(
                    quantity=Sum("quantity"),
                    amount=Sum("amount"),
                )
                already_returned = previous["quantity"] or Decimal("0.000")
                already_refunded = previous["amount"] or Decimal("0.00")
                remaining_quantity = sale_line.quantity - already_returned
                if quantity > remaining_quantity:
                    raise BusinessRuleError(
                        "Return quantity exceeds the sale's unreturned quantity."
                    )
                remaining_amount = sale_line.line_total - already_refunded
                amount = (
                    remaining_amount
                    if quantity == remaining_quantity
                    else quantize_money(
                        sale_line.line_total * quantity / sale_line.quantity
                    )
                )
                if amount <= 0:
                    raise BusinessRuleError(
                        "Returned lines must have a positive refundable value."
                    )
                line_data.append(
                    {
                        "sale_line": sale_line,
                        "quantity": quantity,
                        "amount": amount,
                    }
                )
                total_amount += amount

            total_amount = quantize_money(total_amount)
            credit_reduction = Decimal("0.00")
            if sale.payment_method == Sale.PaymentMethod.CREDIT:
                credit_reduction = min(
                    total_amount,
                    _sale_credit_due(
                        organisation=organisation,
                        sale=sale,
                    ),
                )
            refund_amount = total_amount - credit_reduction
            if refund_amount > 0 and refund_method not in (
                Refund.Method.CASH,
                Refund.Method.MPESA,
            ):
                raise BusinessRuleError(
                    "Choose cash or M-Pesa for the refundable amount."
                )

            sale_return = SaleReturn.objects.create(
                organisation=organisation,
                sale=sale,
                branch=sale.branch,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                reason=reason,
                total_amount=total_amount,
                credit_reduction_amount=credit_reduction,
                refund_amount=refund_amount,
                created_by=actor,
            )

            balances = {}
            product_ids = sorted(
                {item["sale_line"].product_id for item in line_data},
                key=str,
            )
            locked_balances = list(
                StockBalance.objects.for_organisation(organisation)
                .select_for_update()
                .filter(branch=sale.branch, product_id__in=product_ids)
                .order_by("product_id")
            )
            balances.update(
                {balance.product_id: balance for balance in locked_balances}
            )
            for item in line_data:
                sale_line = item["sale_line"]
                return_line = SaleReturnLine.objects.create(
                    organisation=organisation,
                    sale_return=sale_return,
                    sale_line=sale_line,
                    quantity=item["quantity"],
                    amount=item["amount"],
                )
                balance = balances.get(sale_line.product_id)
                if balance is None:
                    balance = StockBalance.objects.create(
                        organisation=organisation,
                        branch=sale.branch,
                        product_id=sale_line.product_id,
                        quantity=Decimal("0.000"),
                        average_cost=sale_line.unit_cost,
                    )
                    balances[sale_line.product_id] = balance
                balance.quantity += item["quantity"]
                balance.version += 1
                balance.save(
                    update_fields=["quantity", "version", "updated_at"]
                )
                StockMovement.objects.create(
                    organisation=organisation,
                    branch=sale.branch,
                    product=sale_line.product,
                    movement_type=StockMovement.MovementType.RETURN,
                    quantity_delta=item["quantity"],
                    unit_cost=sale_line.unit_cost,
                    sale_return_line=return_line,
                    created_by=actor,
                )

            if refund_amount > 0:
                refund_status = (
                    Refund.Status.COMPLETED
                    if refund_method == Refund.Method.CASH
                    else Refund.Status.PENDING
                )
                Refund.objects.create(
                    organisation=organisation,
                    sale_return=sale_return,
                    method=refund_method,
                    status=refund_status,
                    amount=refund_amount,
                    created_by=actor,
                    completed_at=(
                        timezone.now()
                        if refund_status == Refund.Status.COMPLETED
                        else None
                    ),
                )
            AuditEvent.objects.create(
                organisation=organisation,
                actor=actor,
                action="retail.sale.returned",
                target_type="retail.SaleReturn",
                target_id=str(sale_return.pk),
                correlation_id=idempotency_key,
                reason=reason,
                metadata={
                    "sale_id": str(sale.pk),
                    "total_amount": format(total_amount, ".2f"),
                    "credit_reduction": format(credit_reduction, ".2f"),
                    "refund_amount": format(refund_amount, ".2f"),
                    "refund_method": refund_method or "",
                },
            )
            return sale_return, True
    except IntegrityError:
        existing_result = _find_existing(
            SaleReturn,
            organisation,
            idempotency_key,
            request_fingerprint,
        )
        if existing_result is None:
            raise
        return existing_result


def complete_mpesa_refund(
    *,
    organisation,
    refund_id,
    payout_reference,
    actor,
):
    with transaction.atomic():
        refund = (
            Refund.objects.for_organisation(organisation)
            .select_for_update()
            .filter(pk=refund_id)
            .first()
        )
        if refund is None:
            return None, False
        if refund.status == Refund.Status.COMPLETED:
            if refund.payout_reference != payout_reference:
                raise ConflictError("Refund was completed with another payout reference.")
            return refund, False
        if refund.method != Refund.Method.MPESA:
            raise BusinessRuleError("Only pending M-Pesa refunds can be completed.")
        if not payout_reference.strip():
            raise BusinessRuleError("A provider payout reference is required.")
        refund.status = Refund.Status.COMPLETED
        refund.payout_reference = payout_reference.strip()
        refund.completed_at = timezone.now()
        refund.save(
            update_fields=[
                "status",
                "payout_reference",
                "completed_at",
                "updated_at",
            ]
        )
        AuditEvent.objects.create(
            organisation=organisation,
            actor=actor,
            action="retail.refund.mpesa.completed",
            target_type="retail.Refund",
            target_id=str(refund.pk),
            correlation_id=refund.sale_return.idempotency_key,
            metadata={
                "return_id": str(refund.sale_return_id),
                "amount": format(refund.amount, ".2f"),
                "payout_reference": refund.payout_reference,
            },
        )
        return refund, True


def _find_existing(model, organisation, idempotency_key, fingerprint):
    existing = model.objects.for_organisation(organisation).filter(
        idempotency_key=idempotency_key
    ).first()
    if existing is None:
        return None
    return _check_retry(existing, fingerprint)


def receive_goods(
    *,
    organisation,
    branch,
    supplier,
    supplier_reference,
    lines,
    idempotency_key,
    request_fingerprint,
    actor,
):
    try:
        with transaction.atomic():
            existing = (
                GoodsReceipt.objects.for_organisation(organisation)
                .select_for_update()
                .filter(idempotency_key=idempotency_key)
                .first()
            )
            if existing is not None:
                return _check_retry(existing, request_fingerprint)

            receipt = GoodsReceipt.objects.create(
                organisation=organisation,
                branch=branch,
                supplier=supplier,
                supplier_reference=supplier_reference,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                created_by=actor,
            )
            total_cost = Decimal("0.00")
            for line in sorted(lines, key=lambda item: str(item["product"].pk)):
                product = line["product"]
                quantity = line["quantity"]
                unit_cost = line["unit_cost"]
                balance, _ = (
                    StockBalance.objects.for_organisation(organisation)
                    .select_for_update()
                    .get_or_create(
                        branch=branch,
                        product=product,
                        defaults={
                            "organisation": organisation,
                            "quantity": Decimal("0.000"),
                            "average_cost": Decimal("0.00"),
                        },
                    )
                )
                previous_quantity = balance.quantity
                new_quantity = previous_quantity + quantity
                balance.average_cost = quantize_money(
                    (
                        previous_quantity * balance.average_cost
                        + quantity * unit_cost
                    )
                    / new_quantity
                )
                balance.quantity = new_quantity
                balance.version += 1
                balance.save(
                    update_fields=["quantity", "average_cost", "version", "updated_at"]
                )

                line_total = quantize_money(quantity * unit_cost)
                GoodsReceiptLine.objects.create(
                    organisation=organisation,
                    receipt=receipt,
                    product=product,
                    quantity=quantity,
                    unit_cost=unit_cost,
                    line_total=line_total,
                )
                StockMovement.objects.create(
                    organisation=organisation,
                    branch=branch,
                    product=product,
                    movement_type=StockMovement.MovementType.RECEIPT,
                    quantity_delta=quantity,
                    unit_cost=unit_cost,
                    goods_receipt=receipt,
                    created_by=actor,
                )
                total_cost += line_total

            receipt.total_cost = quantize_money(total_cost)
            receipt.save(update_fields=["total_cost", "updated_at"])
            return receipt, True
    except IntegrityError:
        existing_result = _find_existing(
            GoodsReceipt,
            organisation,
            idempotency_key,
            request_fingerprint,
        )
        if existing_result is None:
            raise
        return existing_result


def request_stock_adjustment(
    *,
    organisation,
    branch,
    product,
    quantity_delta,
    expected_stock_version,
    reason,
    idempotency_key,
    request_fingerprint,
    actor,
):
    try:
        with transaction.atomic():
            existing = (
                StockAdjustment.objects.for_organisation(organisation)
                .select_for_update()
                .filter(idempotency_key=idempotency_key)
                .first()
            )
            if existing is not None:
                return _check_retry(existing, request_fingerprint)

            balance, _ = (
                StockBalance.objects.for_organisation(organisation)
                .select_for_update()
                .get_or_create(
                    branch=branch,
                    product=product,
                    defaults={
                        "organisation": organisation,
                        "quantity": Decimal("0.000"),
                        "average_cost": Decimal("0.00"),
                    },
                )
            )
            if balance.version != expected_stock_version:
                raise ConflictError(
                    "Stock changed after it was reviewed; refresh and try again."
                )

            adjustment = StockAdjustment.objects.create(
                organisation=organisation,
                branch=branch,
                product=product,
                quantity_delta=quantity_delta,
                expected_stock_version=expected_stock_version,
                reason=reason,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                requested_by=actor,
            )
            return adjustment, True
    except IntegrityError:
        existing_result = _find_existing(
            StockAdjustment,
            organisation,
            idempotency_key,
            request_fingerprint,
        )
        if existing_result is None:
            raise
        return existing_result


def approve_stock_adjustment(*, organisation, adjustment_id, actor):
    with transaction.atomic():
        adjustment = (
            StockAdjustment.objects.for_organisation(organisation)
            .select_for_update()
            .filter(pk=adjustment_id)
            .first()
        )
        if adjustment is None:
            return None, False
        if adjustment.status == StockAdjustment.Status.APPROVED:
            return adjustment, False
        if adjustment.status != StockAdjustment.Status.REQUESTED:
            raise ConflictError("Only requested adjustments can be approved.")

        balance = (
            StockBalance.objects.for_organisation(organisation)
            .select_for_update()
            .get(branch=adjustment.branch, product=adjustment.product)
        )
        if balance.version != adjustment.expected_stock_version:
            raise ConflictError(
                "Stock changed after the adjustment was requested; "
                "submit a new request."
            )

        new_quantity = balance.quantity + adjustment.quantity_delta
        if new_quantity < 0:
            raise BusinessRuleError("The adjustment would make stock negative.")

        balance.quantity = new_quantity
        balance.version += 1
        balance.save(update_fields=["quantity", "version", "updated_at"])

        adjustment.status = StockAdjustment.Status.APPROVED
        adjustment.reviewed_by = actor
        adjustment.reviewed_at = timezone.now()
        adjustment.save(
            update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"]
        )
        StockMovement.objects.create(
            organisation=organisation,
            branch=adjustment.branch,
            product=adjustment.product,
            movement_type=StockMovement.MovementType.ADJUSTMENT,
            quantity_delta=adjustment.quantity_delta,
            unit_cost=balance.average_cost,
            stock_adjustment=adjustment,
            created_by=actor,
        )
        return adjustment, True


def reject_stock_adjustment(
    *,
    organisation,
    adjustment_id,
    actor,
    review_note="",
):
    with transaction.atomic():
        adjustment = (
            StockAdjustment.objects.for_organisation(organisation)
            .select_for_update()
            .filter(pk=adjustment_id)
            .first()
        )
        if adjustment is None:
            return None, False
        if adjustment.status == StockAdjustment.Status.REJECTED:
            return adjustment, False
        if adjustment.status != StockAdjustment.Status.REQUESTED:
            raise ConflictError("Only requested adjustments can be rejected.")

        adjustment.status = StockAdjustment.Status.REJECTED
        adjustment.review_note = review_note
        adjustment.reviewed_by = actor
        adjustment.reviewed_at = timezone.now()
        adjustment.save(
            update_fields=[
                "status",
                "review_note",
                "reviewed_by",
                "reviewed_at",
                "updated_at",
            ]
        )
        return adjustment, True
