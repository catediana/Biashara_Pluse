from django.urls import path

from . import views

app_name = "reporting"

urlpatterns = [
    path(
        "sales-summary/",
        views.SalesSummaryReportView.as_view(),
        name="sales-summary",
    ),
    path("stock/", views.StockReportView.as_view(), name="stock"),
    path(
        "customer-debt/",
        views.CustomerDebtReportView.as_view(),
        name="customer-debt",
    ),
    path("expenses/", views.ExpenseReportView.as_view(), name="expenses"),
    path("profit/", views.ProfitReportView.as_view(), name="profit"),
]
