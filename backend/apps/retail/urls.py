from django.urls import path

from . import views

app_name = "retail"

urlpatterns = [
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
]
