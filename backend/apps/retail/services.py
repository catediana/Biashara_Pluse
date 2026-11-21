import hashlib
import json
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.retail.models import (
    GoodsReceipt,
    GoodsReceiptLine,
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


def _check_retry(existing, fingerprint):
    if existing.request_fingerprint != fingerprint:
        raise ConflictError(
            "This idempotency key was already used for a different request."
        )
    return existing, False


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
