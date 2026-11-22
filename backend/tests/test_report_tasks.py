from decimal import Decimal

import pytest

from apps.organisations.models import Branch, Organisation
from apps.retail.models import Product, StockBalance
from apps.reporting.tasks import generate_report_task


@pytest.mark.django_db
def test_report_task_is_repeatable_and_rejects_foreign_branch():
    organisation = Organisation.objects.create(
        name="Report task tenant",
        sector=Organisation.Sector.RETAIL,
    )
    branch = Branch.objects.create(organisation=organisation, name="Main")
    product = Product.objects.create(
        organisation=organisation,
        name="Tea",
        sku="REPORT-TASK-TEA",
        selling_price=Decimal("3.00"),
        cost_price=Decimal("2.00"),
        tax_rate=Decimal("0.00"),
    )
    StockBalance.objects.create(
        organisation=organisation,
        branch=branch,
        product=product,
        quantity=Decimal("4.000"),
        average_cost=Decimal("2.00"),
    )

    args = [
        str(organisation.pk),
        "stock",
        {"branch_id": str(branch.pk)},
    ]
    first = generate_report_task.apply(args=args).get(propagate=True)
    repeated = generate_report_task.apply(args=args).get(propagate=True)
    assert first == repeated
    assert first[0]["product_name"] == "Tea"
    assert first[0]["closing_quantity"] == "4.000"

    foreign_organisation = Organisation.objects.create(
        name="Other report tenant",
        sector=Organisation.Sector.RETAIL,
    )
    foreign_branch = Branch.objects.create(
        organisation=foreign_organisation,
        name="Foreign",
    )
    foreign_branch_result = generate_report_task.apply(
        args=[
            str(organisation.pk),
            "stock",
            {"branch_id": str(foreign_branch.pk)},
        ],
        throw=False,
    )
    with pytest.raises(ValueError):
        foreign_branch_result.get(propagate=True)
