from rest_framework.views import APIView

from core.pagination import DefaultPagination
from core.permissions import HasTenantAccess
from core.tenancy import get_active_organisation

from .exports import csv_response
from .serializers import ReportFilterSerializer
from .services import (
    customer_debt_report,
    expense_report,
    profit_report,
    sales_summary,
    stock_report,
)


class ReportAPIView(APIView):
    permission_classes = [HasTenantAccess]
    required_permission = "retail.reports.view"
    required_module = "retail"
    branch_scoped = True
    columns = ()
    filename = "report.csv"

    def get_report(self, organisation, filters):
        raise NotImplementedError

    def get(self, request):
        serializer = ReportFilterSerializer(
            data=request.query_params,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data
        rows = self.get_report(
            get_active_organisation(request),
            filters,
        )
        if filters["export"] == "csv":
            return csv_response(
                filename=self.filename,
                columns=self.columns,
                rows=rows,
            )
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response(page)


class SalesSummaryReportView(ReportAPIView):
    filename = "sales-summary.csv"
    columns = (
        ("date", "Date"),
        ("branch_id", "Branch ID"),
        ("branch_name", "Branch"),
        ("sales_count", "Sales count"),
        ("gross_sales", "Gross sales"),
        ("returned_amount", "Returns"),
        ("net_sales", "Net sales"),
    )

    def get_report(self, organisation, filters):
        return sales_summary(organisation=organisation, filters=filters)


class StockReportView(ReportAPIView):
    filename = "stock-report.csv"
    columns = (
        ("branch_id", "Branch ID"),
        ("branch_name", "Branch"),
        ("product_id", "Product ID"),
        ("product_name", "Product"),
        ("sku", "SKU"),
        ("opening_quantity", "Opening quantity"),
        ("closing_quantity", "Closing quantity"),
        ("quantity_change", "Quantity change"),
        ("average_cost", "Average cost"),
        ("estimated_value", "Estimated value"),
    )

    def get_report(self, organisation, filters):
        return stock_report(organisation=organisation, filters=filters)


class CustomerDebtReportView(ReportAPIView):
    filename = "customer-debt.csv"
    columns = (
        ("customer_id", "Customer ID"),
        ("customer_name", "Customer"),
        ("phone_number", "Phone number"),
        ("credit_sales", "Credit sales"),
        ("collections", "Confirmed collections"),
        ("returns", "Credit reductions"),
        ("outstanding_balance", "Outstanding balance"),
    )

    def get_report(self, organisation, filters):
        return customer_debt_report(organisation=organisation, filters=filters)


class ExpenseReportView(ReportAPIView):
    filename = "expense-report.csv"
    columns = (
        ("expense_id", "Expense ID"),
        ("date", "Date"),
        ("branch_id", "Branch ID"),
        ("branch_name", "Branch"),
        ("category", "Category"),
        ("description", "Description"),
        ("amount", "Amount"),
        ("payment_method", "Payment method"),
        ("created_by", "Created by user ID"),
    )

    def get_report(self, organisation, filters):
        return expense_report(organisation=organisation, filters=filters)


class ProfitReportView(ReportAPIView):
    filename = "profit-report.csv"
    columns = (
        ("date", "Date"),
        ("branch_id", "Branch ID"),
        ("branch_name", "Branch"),
        ("sales_count", "Sales count"),
        ("net_sales", "Net sales"),
        ("net_cost_of_goods_sold", "Net cost of goods sold"),
        ("expenses", "Expenses"),
        ("net_profit", "Net profit"),
    )

    def get_report(self, organisation, filters):
        return profit_report(organisation=organisation, filters=filters)
