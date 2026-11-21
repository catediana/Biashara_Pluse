import hashlib
import json
import uuid
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.retail.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    Product,
    Receipt,
    Sale,
    SaleLine,
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
    return _fingerprint(
        {
            "branch": str(data["branch"].pk),
            "shift": str(data["shift"].pk),
            "payment_method": data["payment_method"],
            "amount_tendered": (
                _decimal_text(data["amount_tendered"])
                if data.get("amount_tendered") is not None
                else None
            ),
            "lines": [
                {
                    "product": str(line["product"].pk),
                    "quantity": _decimal_text(line["quantity"]),
                }
                for line in lines
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
    return {
        "receipt_number": sale.sale_number,
        "sale_id": str(sale.pk),
        "organisation": sale.organisation.name,
        "branch": sale.branch.name,
        "date": sale.created_at.isoformat(),
        "cashier": sale.cashier.get_full_name() or sale.cashier.get_username(),
        "payment_method": sale.payment_method,
        "payment_status": sale.status,
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
    }


def _check_retry(existing, fingerprint):
    if existing.request_fingerprint != fingerprint:
        raise ConflictError(
            "This idempotency key was already used for a different request."
        )
    return existing, False


def checkout(
    *,
    organisation,
    branch,
    shift,
    lines,
    payment_method,
    amount_tendered,
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
            elif payment_method == Sale.PaymentMethod.MPESA:
                if amount_tendered is not None:
                    raise BusinessRuleError(
                        "Pending M-Pesa checkout does not accept a cash tender."
                    )
                tendered = None
                change_due = Decimal("0.00")
                sale_status = Sale.Status.PENDING_PAYMENT
                completed_at = None
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
                sale_number=sale_number,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                payment_method=payment_method,
                status=sale_status,
                subtotal=subtotal,
                tax_total=tax_total,
                total=total,
                amount_tendered=tendered,
                change_due=change_due,
                completed_at=completed_at,
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
