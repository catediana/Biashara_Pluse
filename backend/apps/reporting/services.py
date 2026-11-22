from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.retail.models import (
    Expense,
    Payment,
    PaymentAllocation,
    Sale,
    SaleLine,
    SaleReturn,
    SaleReturnLine,
    StockBalance,
    StockMovement,
)
from core.money import quantize_money


ZERO = Decimal("0.00")


def _date_boundaries(filters):
    current_timezone = timezone.get_current_timezone()
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    start = (
        timezone.make_aware(
            datetime.combine(from_date, time.min),
            current_timezone,
        )
        if from_date
        else None
    )
    end = (
        timezone.make_aware(
            datetime.combine(to_date + timedelta(days=1), time.min),
            current_timezone,
        )
        if to_date
        else None
    )
    return start, end


def _filter_date_range(queryset, field, filters):
    start, end = _date_boundaries(filters)
    if start is not None:
        queryset = queryset.filter(**{f"{field}__gte": start})
    if end is not None:
        queryset = queryset.filter(**{f"{field}__lt": end})
    return queryset


def _filter_branch(queryset, filters, field="branch"):
    branch = filters.get("branch")
    if branch is not None:
        queryset = queryset.filter(**{field: branch})
    return queryset


def _group_key(row):
    return row["date"], row["branch_id"]


def _add_amount(rows, source, field, target):
    for item in source:
        key = _group_key(item)
        row = rows.setdefault(
            key,
            {
                "date": item["date"],
                "branch_id": str(item["branch_id"]),
                "branch_name": item["branch_name"],
                "sales_count": 0,
                "gross_sales": ZERO,
                "returned_amount": ZERO,
                "cost_of_goods_sold": ZERO,
                "returned_cost": ZERO,
                "expenses": ZERO,
            },
        )
        if target == "sales_count":
            row[target] += item[field]
        else:
            row[target] += item[field] or ZERO


def _ordered_rollup(rows):
    return [
        rows[key]
        for key in sorted(rows, key=lambda item: (item[0], str(item[1])))
    ]


def sales_summary(*, organisation, filters):
    sales = _filter_branch(
        Sale.objects.for_organisation(organisation)
        .filter(status=Sale.Status.POSTED),
        filters,
    )
    sales = _filter_date_range(sales, "created_at", filters)
    sales_rows = list(
        sales.values(
            "branch_id",
            day=TruncDate("created_at"),
            branch_name=F("branch__name"),
        )
        .annotate(
            sales_count=Count("pk"),
            gross_sales=Sum("total"),
        )
        .order_by("day", "branch_id")
    )
    returns = _filter_branch(
        SaleReturn.objects.for_organisation(organisation),
        filters,
    )
    returns = _filter_date_range(returns, "created_at", filters)
    return_rows = list(
        returns.values(
            "branch_id",
            day=TruncDate("created_at"),
            branch_name=F("branch__name"),
        )
        .annotate(returned_amount=Sum("total_amount"))
        .order_by("day", "branch_id")
    )

    rows = {}
    for item in sales_rows:
        rows[(item["day"], item["branch_id"])] = {
            "date": item["day"],
            "branch_id": str(item["branch_id"]),
            "branch_name": item["branch_name"],
            "sales_count": item["sales_count"],
            "gross_sales": item["gross_sales"] or ZERO,
            "returned_amount": ZERO,
        }
    for item in return_rows:
        key = (item["day"], item["branch_id"])
        row = rows.setdefault(
            key,
            {
                "date": item["day"],
                "branch_id": str(item["branch_id"]),
                "branch_name": item["branch_name"],
                "sales_count": 0,
                "gross_sales": ZERO,
                "returned_amount": ZERO,
            },
        )
        row["returned_amount"] += item["returned_amount"] or ZERO
    result = _ordered_rollup(rows)
    for row in result:
        row["net_sales"] = quantize_money(
            row["gross_sales"] - row["returned_amount"]
        )
    return result


def stock_report(*, organisation, filters):
    balances = _filter_branch(
        StockBalance.objects.for_organisation(organisation).select_related(
            "branch",
            "product",
        ),
        filters,
    )
    balance_rows = list(balances)
    if not balance_rows:
        return []

    movement_queryset = StockMovement.objects.for_organisation(organisation)
    if filters.get("branch") is not None:
        movement_queryset = movement_queryset.filter(branch=filters["branch"])
    start, end = _date_boundaries(filters)
    after_start = {}
    after_end = {}
    branch_ids = {balance.branch_id for balance in balance_rows}
    product_ids = {balance.product_id for balance in balance_rows}
    relevant_movements = movement_queryset.filter(
        branch_id__in=branch_ids,
        product_id__in=product_ids,
    )
    if start is not None:
        after_start = {
            (row["branch_id"], row["product_id"]): row["total"] or Decimal("0")
            for row in relevant_movements.filter(created_at__gte=start)
            .values("branch_id", "product_id")
            .annotate(total=Sum("quantity_delta"))
        }
    if end is not None:
        after_end = {
            (row["branch_id"], row["product_id"]): row["total"] or Decimal("0")
            for row in relevant_movements.filter(created_at__gte=end)
            .values("branch_id", "product_id")
            .annotate(total=Sum("quantity_delta"))
        }

    rows = []
    for balance in balance_rows:
        key = (balance.branch_id, balance.product_id)
        closing = (
            balance.quantity - after_end.get(key, Decimal("0"))
            if end is not None
            else balance.quantity
        )
        opening = (
            balance.quantity - after_start.get(key, Decimal("0"))
            if start is not None
            else closing
        )
        rows.append(
            {
                "branch_id": str(balance.branch_id),
                "branch_name": balance.branch.name,
                "product_id": str(balance.product_id),
                "product_name": balance.product.name,
                "sku": balance.product.sku,
                "opening_quantity": opening,
                "closing_quantity": closing,
                "quantity_change": closing - opening,
                "average_cost": balance.average_cost,
                "estimated_value": quantize_money(
                    closing * balance.average_cost
                ),
            }
        )
    return sorted(
        rows,
        key=lambda item: (
            item["branch_name"].casefold(),
            item["product_name"].casefold(),
            item["product_id"],
        ),
    )


def customer_debt_report(*, organisation, filters):
    sales = Sale.objects.for_organisation(organisation).filter(
        payment_method=Sale.PaymentMethod.CREDIT,
        status=Sale.Status.POSTED,
        customer__isnull=False,
    )
    sales = _filter_branch(sales, filters)
    sales = _filter_date_range(sales, "created_at", filters)
    credit_rows = sales.values(
        "customer_id",
        customer_name=F("customer__name"),
        phone_number=F("customer__phone_number"),
    ).annotate(credit_sales=Sum("credit_amount"))
    credits = {
        row["customer_id"]: {
            "customer_id": str(row["customer_id"]),
            "customer_name": row["customer_name"],
            "phone_number": row["phone_number"],
            "credit_sales": row["credit_sales"] or ZERO,
            "collections": ZERO,
            "returns": ZERO,
        }
        for row in credit_rows
    }
    if not credits:
        return []

    allocations = PaymentAllocation.objects.for_organisation(
        organisation
    ).filter(
        sale__in=sales,
        payment__purpose=Payment.Purpose.COLLECTION,
        payment__status=Payment.Status.CONFIRMED,
    )
    _, end = _date_boundaries(filters)
    if end is not None:
        allocations = allocations.filter(payment__confirmed_at__lt=end)
    collection_rows = allocations.values("sale__customer_id").annotate(
        total=Sum("amount")
    )
    for item in collection_rows:
        credits[item["sale__customer_id"]]["collections"] = item["total"] or ZERO

    returns = SaleReturn.objects.for_organisation(organisation).filter(sale__in=sales)
    if end is not None:
        returns = returns.filter(created_at__lt=end)
    for item in returns.values("sale__customer_id").annotate(
        total=Sum("credit_reduction_amount")
    ):
        credits[item["sale__customer_id"]]["returns"] = item["total"] or ZERO

    rows = []
    for item in credits.values():
        item["outstanding_balance"] = max(
            item["credit_sales"] - item["collections"] - item["returns"],
            ZERO,
        )
        if item["outstanding_balance"] > 0:
            rows.append(item)
    return sorted(
        rows,
        key=lambda item: (
            -item["outstanding_balance"],
            item["customer_name"].casefold(),
        ),
    )


def expense_report(*, organisation, filters):
    expenses = _filter_branch(
        Expense.objects.for_organisation(organisation).select_related(
            "branch",
            "created_by",
        ),
        filters,
    )
    expenses = _filter_date_range(expenses, "created_at", filters)
    return [
        {
            "expense_id": str(expense.pk),
            "date": timezone.localtime(expense.created_at).date(),
            "branch_id": str(expense.branch_id),
            "branch_name": expense.branch.name,
            "category": expense.category,
            "description": expense.description,
            "amount": expense.amount,
            "payment_method": expense.payment_method,
            "created_by": expense.created_by_id,
        }
        for expense in expenses.order_by("-created_at", "pk")
    ]


def profit_report(*, organisation, filters):
    sales = _filter_branch(
        Sale.objects.for_organisation(organisation).filter(
            status=Sale.Status.POSTED
        ),
        filters,
    )
    sales = _filter_date_range(sales, "created_at", filters)
    cost_expression = ExpressionWrapper(
        F("unit_cost") * F("quantity"),
        output_field=DecimalField(max_digits=30, decimal_places=5),
    )
    sales_by_date = sales.values(
        "branch_id",
        day=TruncDate("created_at"),
        branch_name=F("branch__name"),
    ).annotate(
        sales_count=Count("pk"),
        gross_sales=Sum("total"),
    )
    cogs_by_date = _filter_date_range(
        SaleLine.objects.for_organisation(organisation).filter(
            sale__in=sales
        ),
        "sale__created_at",
        filters,
    ).values(
        day=TruncDate("sale__created_at"),
        branch_id=F("sale__branch_id"),
        branch_name=F("sale__branch__name"),
    ).annotate(cost=Sum(cost_expression))
    returns = _filter_branch(
        SaleReturn.objects.for_organisation(organisation),
        filters,
    )
    returns = _filter_date_range(returns, "created_at", filters)
    returns_by_date = returns.values(
        "branch_id",
        day=TruncDate("created_at"),
        branch_name=F("branch__name"),
    ).annotate(returned_amount=Sum("total_amount"))
    return_costs = _filter_date_range(
        SaleReturnLine.objects.for_organisation(organisation).filter(
            sale_return__in=returns
        ),
        "created_at",
        filters,
    ).values(
        day=TruncDate("created_at"),
        branch_id=F("sale_return__branch_id"),
        branch_name=F("sale_return__branch__name"),
    ).annotate(
        cost=Sum(
            ExpressionWrapper(
                F("sale_line__unit_cost") * F("quantity"),
                output_field=DecimalField(max_digits=30, decimal_places=5),
            )
        )
    )
    expenses = _filter_branch(
        Expense.objects.for_organisation(organisation),
        filters,
    )
    expenses = _filter_date_range(expenses, "created_at", filters)
    expenses_by_date = expenses.values(
        "branch_id",
        day=TruncDate("created_at"),
        branch_name=F("branch__name"),
    ).annotate(total=Sum("amount"))

    rows = {}
    for source, field, target in (
        (sales_by_date, "sales_count", "sales_count"),
        (sales_by_date, "gross_sales", "gross_sales"),
        (cogs_by_date, "cost", "cost_of_goods_sold"),
        (returns_by_date, "returned_amount", "returned_amount"),
        (return_costs, "cost", "returned_cost"),
        (expenses_by_date, "total", "expenses"),
    ):
        normalized = (
            {
                "date": item["day"],
                "branch_id": item["branch_id"],
                "branch_name": item["branch_name"],
                field: item[field],
            }
            for item in source
        )
        _add_amount(rows, normalized, field, target)

    result = _ordered_rollup(rows)
    for row in result:
        net_sales = row["gross_sales"] - row["returned_amount"]
        net_cost = row["cost_of_goods_sold"] - row["returned_cost"]
        row["net_sales"] = quantize_money(net_sales)
        row["net_cost_of_goods_sold"] = quantize_money(net_cost)
        row["expenses"] = quantize_money(row["expenses"])
        row["net_profit"] = quantize_money(
            net_sales - net_cost - row["expenses"]
        )
        del row["returned_cost"]
        del row["cost_of_goods_sold"]
        del row["gross_sales"]
        del row["returned_amount"]
    return result
