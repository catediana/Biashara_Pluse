import json
from datetime import date
from uuid import UUID

from celery import shared_task
from django.db import OperationalError

from apps.organisations.models import Branch, Organisation

from .services import (
    customer_debt_report,
    expense_report,
    profit_report,
    sales_summary,
    stock_report,
)


REPORTS = {
    "sales_summary": sales_summary,
    "stock": stock_report,
    "customer_debt": customer_debt_report,
    "expenses": expense_report,
    "profit": profit_report,
}


def _report_filters(organisation, filters):
    if not isinstance(filters, dict):
        raise ValueError("Report filters must be an object.")
    allowed = {"branch_id", "from_date", "to_date"}
    unknown = set(filters) - allowed
    if unknown:
        raise ValueError(f"Unsupported report filters: {', '.join(sorted(unknown))}.")

    parsed = {}
    branch_id = filters.get("branch_id")
    if branch_id is not None:
        try:
            branch_id = UUID(str(branch_id))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("branch_id must be a UUID.") from exc
        branch = Branch.objects.for_organisation(organisation).filter(
            pk=branch_id,
            is_active=True,
        ).first()
        if branch is None:
            raise ValueError("Branch does not belong to this organisation.")
        parsed["branch"] = branch

    for key in ("from_date", "to_date"):
        value = filters.get(key)
        if value is not None:
            try:
                parsed[key] = date.fromisoformat(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} must use YYYY-MM-DD format.") from exc
    if (
        parsed.get("from_date")
        and parsed.get("to_date")
        and parsed["from_date"] > parsed["to_date"]
    ):
        raise ValueError("from_date must be on or before to_date.")
    return parsed


@shared_task(
    bind=True,
    name="reporting.generate_report",
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def generate_report_task(self, organisation_id, report_type, filters=None):
    report = REPORTS.get(report_type)
    if report is None:
        raise ValueError(f"Unsupported report type: {report_type}.")
    try:
        organisation_id = UUID(str(organisation_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("organisation_id must be a UUID.") from exc
    organisation = Organisation.objects.get(pk=organisation_id, is_active=True)
    rows = report(
        organisation=organisation,
        filters=_report_filters(
            organisation,
            {} if filters is None else filters,
        ),
    )
    return json.loads(json.dumps(rows, default=str))
