from django.http import Http404
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import DefaultPagination
from core.permissions import HasTenantAccess
from core.tenancy import get_active_organisation

from .models import Product, StockAdjustment
from .serializers import (
    GoodsReceiptCreateSerializer,
    GoodsReceiptReadSerializer,
    ProductSerializer,
    StockAdjustmentCreateSerializer,
    StockAdjustmentDecisionSerializer,
    StockAdjustmentReadSerializer,
)
from .services import (
    approve_stock_adjustment,
    goods_receipt_fingerprint,
    receive_goods,
    reject_stock_adjustment,
    request_stock_adjustment,
    stock_adjustment_fingerprint,
)


class RetailAPIView(APIView):
    permission_classes = [HasTenantAccess]
    required_module = "retail"

    def get_permissions(self):
        self.required_permission = self.get_required_permission()
        return super().get_permissions()

    def get_required_permission(self):
        raise NotImplementedError


class ProductListCreateView(RetailAPIView):
    permission_by_method = {
        "GET": "retail.products.view",
        "HEAD": "retail.products.view",
        "OPTIONS": "retail.products.view",
        "POST": "retail.products.create",
    }

    def get_required_permission(self):
        return self.permission_by_method.get(
            self.request.method, "retail.products.view"
        )

    def get(self, request):
        queryset = Product.objects.for_organisation(
            get_active_organisation(request)
        ).filter(is_active=True)
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(sku__icontains=search)
                | Q(barcode__icontains=search)
            )

        paginator = DefaultPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        data = ProductSerializer(
            page,
            many=True,
            context={"request": request},
        ).data
        return paginator.get_paginated_response(data)

    def post(self, request):
        serializer = ProductSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        return Response(
            ProductSerializer(product, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class ProductDetailView(RetailAPIView):
    permission_by_method = {
        "GET": "retail.products.view",
        "HEAD": "retail.products.view",
        "OPTIONS": "retail.products.view",
        "PATCH": "retail.products.update",
    }

    def get_required_permission(self):
        return self.permission_by_method.get(
            self.request.method, "retail.products.view"
        )

    def get_product(self, request, pk):
        product = (
            Product.objects.for_organisation(get_active_organisation(request))
            .filter(pk=pk)
            .first()
        )
        if product is None:
            raise Http404
        return product

    def get(self, request, pk):
        product = self.get_product(request, pk)
        return Response(
            ProductSerializer(product, context={"request": request}).data
        )

    def patch(self, request, pk):
        product = self.get_product(request, pk)
        serializer = ProductSerializer(
            product,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        return Response(
            ProductSerializer(product, context={"request": request}).data
        )


class GoodsReceiptCreateView(RetailAPIView):
    required_permission = "retail.stock.receive"
    branch_scoped = True

    def get_required_permission(self):
        return self.required_permission

    def post(self, request):
        serializer = GoodsReceiptCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        fingerprint = goods_receipt_fingerprint(data)
        receipt, created = receive_goods(
            organisation=get_active_organisation(request),
            branch=data["branch"],
            supplier=data["supplier"],
            supplier_reference=data.get("supplier_reference", ""),
            lines=data["lines"],
            idempotency_key=data["idempotency_key"],
            request_fingerprint=fingerprint,
            actor=request.user,
        )
        response_data = GoodsReceiptReadSerializer(receipt).data
        return Response(
            response_data,
            status=(
                status.HTTP_201_CREATED if created else status.HTTP_200_OK
            ),
        )


class StockAdjustmentCreateView(RetailAPIView):
    required_permission = "retail.stock.adjustment.request"
    branch_scoped = True

    def get_required_permission(self):
        return self.required_permission

    def post(self, request):
        serializer = StockAdjustmentCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        fingerprint = stock_adjustment_fingerprint(data)
        adjustment, created = request_stock_adjustment(
            organisation=get_active_organisation(request),
            branch=data["branch"],
            product=data["product"],
            quantity_delta=data["quantity_delta"],
            expected_stock_version=data["expected_stock_version"],
            reason=data["reason"],
            idempotency_key=data["idempotency_key"],
            request_fingerprint=fingerprint,
            actor=request.user,
        )
        return Response(
            StockAdjustmentReadSerializer(adjustment).data,
            status=(
                status.HTTP_201_CREATED if created else status.HTTP_200_OK
            ),
        )


class StockAdjustmentDecisionView(RetailAPIView):
    branch_scoped = True
    branch_object_lookup = True

    def get_required_permission(self):
        action = self.kwargs["action"]
        if action in ("approve", "reject"):
            return f"retail.stock.adjustment.{action}"
        return "retail.stock.adjustment.invalid"

    def post(self, request, pk, action):
        organisation = get_active_organisation(request)
        adjustment = (
            StockAdjustment.objects.for_organisation(organisation)
            .select_related("branch", "product")
            .filter(pk=pk)
            .first()
        )
        if adjustment is None:
            raise Http404
        self.check_object_permissions(request, adjustment)

        if action == "approve":
            note_serializer = StockAdjustmentDecisionSerializer(data=request.data)
            note_serializer.is_valid(raise_exception=True)
            adjustment, _ = approve_stock_adjustment(
                organisation=organisation,
                adjustment_id=adjustment.pk,
                actor=request.user,
            )
        elif action == "reject":
            note_serializer = StockAdjustmentDecisionSerializer(data=request.data)
            note_serializer.is_valid(raise_exception=True)
            adjustment, _ = reject_stock_adjustment(
                organisation=organisation,
                adjustment_id=adjustment.pk,
                actor=request.user,
                review_note=note_serializer.validated_data.get(
                    "review_note", ""
                ),
            )
        else:
            raise Http404
        if adjustment is None:
            raise Http404
        return Response(
            StockAdjustmentReadSerializer(adjustment).data,
            status=status.HTTP_200_OK,
        )
