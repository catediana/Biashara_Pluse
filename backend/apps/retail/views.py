from django.http import Http404
from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.integrations.mpesa import MpesaProviderError
from core.pagination import DefaultPagination
from core.permissions import HasTenantAccess
from core.tenancy import get_active_organisation

from .models import Customer, Payment, Product, Refund, Sale, StockAdjustment
from .serializers import (
    CheckoutSerializer,
    CustomerCollectionSerializer,
    CustomerSerializer,
    GoodsReceiptCreateSerializer,
    GoodsReceiptReadSerializer,
    PaymentInitiateSerializer,
    PaymentReadSerializer,
    ProductSerializer,
    RefundCompleteSerializer,
    RefundReadSerializer,
    ReceiptReadSerializer,
    SaleReadSerializer,
    SaleReturnCreateSerializer,
    SaleReturnReadSerializer,
    StockAdjustmentCreateSerializer,
    StockAdjustmentDecisionSerializer,
    StockAdjustmentReadSerializer,
)
from .services import (
    approve_stock_adjustment,
    collection_fingerprint,
    complete_mpesa_refund,
    checkout,
    checkout_fingerprint,
    process_mpesa_callback,
    record_customer_collection,
    goods_receipt_fingerprint,
    receive_goods,
    reject_stock_adjustment,
    request_stock_adjustment,
    return_fingerprint,
    return_sale,
    start_mpesa_payment,
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


class CheckoutView(RetailAPIView):
    required_permission = "retail.sales.checkout"
    branch_scoped = True

    def get_required_permission(self):
        return self.required_permission

    def post(self, request):
        serializer = CheckoutSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        fingerprint = checkout_fingerprint(data)
        sale, created = checkout(
            organisation=get_active_organisation(request),
            branch=data["branch"],
            shift=data["shift"],
            lines=data["lines"],
            payment_method=data["payment_method"],
            amount_tendered=data.get("amount_tendered"),
            customer=data.get("customer"),
            payment_parts=data.get("payments", []),
            idempotency_key=data["idempotency_key"],
            request_fingerprint=fingerprint,
            actor=request.user,
        )
        sale = (
            type(sale).objects.for_organisation(
                get_active_organisation(request)
            )
            .select_related("organisation", "branch", "shift", "cashier")
            .prefetch_related("lines__product", "payments__allocations")
            .get(pk=sale.pk)
        )
        response_data = SaleReadSerializer(sale).data
        return Response(
            response_data,
            status=(
                status.HTTP_201_CREATED if created else status.HTTP_200_OK
            ),
        )


class CustomerListCreateView(RetailAPIView):
    permission_by_method = {
        "GET": "retail.customers.view",
        "HEAD": "retail.customers.view",
        "OPTIONS": "retail.customers.view",
        "POST": "retail.customers.create",
    }

    def get_required_permission(self):
        return self.permission_by_method.get(
            self.request.method, "retail.customers.view"
        )

    def get(self, request):
        customers = Customer.objects.for_organisation(
            get_active_organisation(request)
        ).filter(is_active=True)
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(customers, request, view=self)
        return paginator.get_paginated_response(
            CustomerSerializer(
                page,
                many=True,
                context={"request": request},
            ).data
        )

    def post(self, request):
        serializer = CustomerSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        customer = serializer.save()
        return Response(
            CustomerSerializer(
                customer,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class CustomerCollectionView(RetailAPIView):
    required_permission = "retail.sales.collection"
    branch_scoped = True

    def get_required_permission(self):
        return self.required_permission

    def post(self, request, customer_pk):
        organisation = get_active_organisation(request)
        customer = (
            Customer.objects.for_organisation(organisation)
            .filter(pk=customer_pk, is_active=True)
            .first()
        )
        if customer is None:
            raise Http404
        serializer = CustomerCollectionSerializer(
            data=request.data,
            context={"request": request, "customer": customer},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        fingerprint = collection_fingerprint(data)
        payment, created = record_customer_collection(
            organisation=organisation,
            customer=customer,
            branch=data["branch"],
            shift=data["shift"],
            method=data["method"],
            amount=data["amount"],
            allocations=data["allocations"],
            phone_number=data.get("phone_number", ""),
            idempotency_key=data["idempotency_key"],
            request_fingerprint=fingerprint,
            actor=request.user,
        )
        return Response(
            PaymentReadSerializer(payment).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class MpesaPaymentInitiateView(RetailAPIView):
    required_permission = "retail.sales.payment"
    branch_scoped = True
    branch_object_lookup = True
    throttle_scope = "retail_payment_initiate"

    def get_required_permission(self):
        return self.required_permission

    def post(self, request, pk):
        organisation = get_active_organisation(request)
        payment = (
            Payment.objects.for_organisation(organisation)
            .filter(pk=pk)
            .first()
        )
        if payment is None:
            raise Http404
        self.check_object_permissions(request, payment)
        serializer = PaymentInitiateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payment, created = start_mpesa_payment(
                organisation=organisation,
                payment_id=payment.pk,
                phone_number=serializer.validated_data["phone_number"],
                actor=request.user,
            )
        except MpesaProviderError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if payment is None:
            raise Http404
        return Response(
            PaymentReadSerializer(payment).data,
            status=status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK,
        )


class MpesaCallbackView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "mpesa_callback"

    def post(self, request):
        try:
            payment, processed = process_mpesa_callback(request.data)
        except MpesaProviderError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            {
                "status": payment.status,
                "duplicate": not processed,
            },
            status=status.HTTP_200_OK,
        )


class SaleReturnCreateView(RetailAPIView):
    required_permission = "retail.sales.return"
    branch_scoped = True
    branch_object_lookup = True

    def get_required_permission(self):
        return self.required_permission

    def post(self, request, pk):
        organisation = get_active_organisation(request)
        sale = (
            Sale.objects.for_organisation(organisation)
            .select_related("branch", "customer")
            .filter(pk=pk)
            .first()
        )
        if sale is None:
            raise Http404
        self.check_object_permissions(request, sale)
        serializer = SaleReturnCreateSerializer(
            data=request.data,
            context={"request": request, "sale": sale},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        fingerprint = return_fingerprint(data, sale_id=sale.pk)
        sale_return, created = return_sale(
            organisation=organisation,
            sale_id=sale.pk,
            lines=data["lines"],
            reason=data["reason"],
            refund_method=data.get("refund_method"),
            idempotency_key=data["idempotency_key"],
            request_fingerprint=fingerprint,
            actor=request.user,
        )
        if sale_return is None:
            raise Http404
        return Response(
            SaleReturnReadSerializer(sale_return).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class RefundCompleteView(RetailAPIView):
    required_permission = "retail.sales.refund"
    branch_scoped = True
    branch_object_lookup = True

    def get_required_permission(self):
        return self.required_permission

    def post(self, request, pk):
        organisation = get_active_organisation(request)
        refund = (
            Refund.objects.for_organisation(organisation)
            .select_related("sale_return")
            .filter(pk=pk)
            .first()
        )
        if refund is None:
            raise Http404
        self.check_object_permissions(request, refund)
        serializer = RefundCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        refund, _ = complete_mpesa_refund(
            organisation=organisation,
            refund_id=refund.pk,
            payout_reference=serializer.validated_data["payout_reference"],
            actor=request.user,
        )
        if refund is None:
            raise Http404
        return Response(RefundReadSerializer(refund).data)


class SaleReceiptView(RetailAPIView):
    required_permission = "retail.sales.view"
    branch_scoped = True
    branch_object_lookup = True

    def get_required_permission(self):
        return self.required_permission

    def get(self, request, pk):
        sale = (
            Sale.objects.for_organisation(get_active_organisation(request))
            .select_related("branch", "receipt")
            .filter(pk=pk)
            .first()
        )
        if sale is None:
            raise Http404
        self.check_object_permissions(request, sale)
        return Response(ReceiptReadSerializer(sale.receipt).data)
