from django.urls import path

from . import views

app_name = "retail"

urlpatterns = [
    path("customers/", views.CustomerListCreateView.as_view(), name="customer-list"),
    path(
        "customers/<uuid:customer_pk>/collections/",
        views.CustomerCollectionView.as_view(),
        name="customer-collection",
    ),
    path("products/", views.ProductListCreateView.as_view(), name="product-list"),
    path(
        "products/<uuid:pk>/",
        views.ProductDetailView.as_view(),
        name="product-detail",
    ),
    path(
        "goods-receipts/",
        views.GoodsReceiptCreateView.as_view(),
        name="goods-receipt-create",
    ),
    path(
        "stock-adjustments/",
        views.StockAdjustmentCreateView.as_view(),
        name="stock-adjustment-create",
    ),
    path(
        "stock-adjustments/<uuid:pk>/<str:action>/",
        views.StockAdjustmentDecisionView.as_view(),
        name="stock-adjustment-decision",
    ),
    path("shifts/", views.ShiftListView.as_view(), name="shift-list"),
    path("shifts/open/", views.ShiftOpenView.as_view(), name="shift-open"),
    path(
        "shifts/<uuid:pk>/close/",
        views.ShiftCloseView.as_view(),
        name="shift-close",
    ),
    path("expenses/", views.ExpenseListCreateView.as_view(), name="expense-list"),
    path("checkout/", views.CheckoutView.as_view(), name="checkout"),
    path(
        "payments/<uuid:pk>/stk-push/",
        views.MpesaPaymentInitiateView.as_view(),
        name="mpesa-payment-initiate",
    ),
    path(
        "mpesa/callback/",
        views.MpesaCallbackView.as_view(),
        name="mpesa-callback",
    ),
    path(
        "sales/<uuid:pk>/returns/",
        views.SaleReturnCreateView.as_view(),
        name="sale-return-create",
    ),
    path(
        "refunds/<uuid:pk>/complete/",
        views.RefundCompleteView.as_view(),
        name="refund-complete",
    ),
    path(
        "sales/<uuid:pk>/receipt/",
        views.SaleReceiptView.as_view(),
        name="sale-receipt",
    ),
]
