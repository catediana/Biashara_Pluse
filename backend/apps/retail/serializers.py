from decimal import Decimal
from uuid import UUID

from rest_framework import serializers

from apps.organisations.models import Branch

from .models import (
    Category,
    Customer,
    GoodsReceipt,
    GoodsReceiptLine,
    Product,
    Payment,
    PaymentAllocation,
    Receipt,
    Refund,
    Sale,
    SaleLine,
    SaleReturn,
    SaleReturnLine,
    StockAdjustment,
    Shift,
    Supplier,
)


class ExactDecimalField(serializers.DecimalField):
    def to_internal_value(self, data):
        if isinstance(data, (bool, float)):
            raise serializers.ValidationError(
                "Send decimal values as strings or integers."
            )
        return super().to_internal_value(data)


class ProductSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.none(),
        required=False,
        allow_null=True,
    )
    selling_price = ExactDecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0"),
    )
    cost_price = ExactDecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0"),
    )
    tax_rate = ExactDecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        required=False,
    )
    reorder_level = ExactDecimalField(
        max_digits=16,
        decimal_places=3,
        min_value=Decimal("0"),
        required=False,
    )

    class Meta:
        model = Product
        fields = [
            "id",
            "category",
            "name",
            "sku",
            "barcode",
            "unit",
            "selling_price",
            "cost_price",
            "tax_rate",
            "reorder_level",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        validators = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        organisation = self.context["request"].active_organisation
        self.fields["category"].queryset = Category.objects.for_organisation(
            organisation
        ).filter(is_active=True)

    def validate(self, attrs):
        organisation = self.context["request"].active_organisation
        for field in ("sku", "barcode"):
            value = attrs.get(field)
            if value:
                products = Product.objects.for_organisation(organisation).filter(
                    **{field: value}
                )
                if self.instance is not None:
                    products = products.exclude(pk=self.instance.pk)
                if products.exists():
                    raise serializers.ValidationError(
                        {field: "A product with this value already exists."}
                    )
        return attrs

    def create(self, validated_data):
        validated_data["organisation"] = self.context[
            "request"
        ].active_organisation
        return super().create(validated_data)


class GoodsReceiptLineInputSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.none())
    quantity = ExactDecimalField(
        max_digits=16,
        decimal_places=3,
        min_value=Decimal("0"),
    )
    unit_cost = ExactDecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0"),
    )

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class GoodsReceiptCreateSerializer(serializers.Serializer):
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.none())
    supplier = serializers.PrimaryKeyRelatedField(queryset=Supplier.objects.none())
    supplier_reference = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
    )
    lines = GoodsReceiptLineInputSerializer(many=True, allow_empty=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        organisation = self.context["request"].active_organisation
        self.fields["branch"].queryset = Branch.objects.for_organisation(
            organisation
        ).filter(is_active=True)
        self.fields["supplier"].queryset = Supplier.objects.for_organisation(
            organisation
        ).filter(is_active=True)
        self.fields["lines"].child.fields["product"].queryset = (
            Product.objects.for_organisation(organisation).filter(is_active=True)
        )

    def validate_lines(self, lines):
        product_ids = [line["product"].pk for line in lines]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError(
                "Each product may appear only once per goods receipt."
            )
        return lines

    def validate(self, attrs):
        raw_key = self.context["request"].headers.get("Idempotency-Key")
        try:
            attrs["idempotency_key"] = UUID(raw_key)
        except (TypeError, ValueError, AttributeError) as exc:
            raise serializers.ValidationError(
                {"idempotency_key": "A valid Idempotency-Key header is required."}
            ) from exc
        return attrs


class GoodsReceiptLineReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoodsReceiptLine
        fields = ["id", "product", "quantity", "unit_cost", "line_total"]


class GoodsReceiptReadSerializer(serializers.ModelSerializer):
    lines = GoodsReceiptLineReadSerializer(many=True, read_only=True)

    class Meta:
        model = GoodsReceipt
        fields = [
            "id",
            "branch",
            "supplier",
            "supplier_reference",
            "idempotency_key",
            "total_cost",
            "status",
            "received_at",
            "lines",
        ]


class StockAdjustmentCreateSerializer(serializers.Serializer):
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.none())
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.none())
    quantity_delta = ExactDecimalField(
        max_digits=16,
        decimal_places=3,
    )
    expected_stock_version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=255, trim_whitespace=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        organisation = self.context["request"].active_organisation
        self.fields["branch"].queryset = Branch.objects.for_organisation(
            organisation
        ).filter(is_active=True)
        self.fields["product"].queryset = Product.objects.for_organisation(
            organisation
        ).filter(is_active=True)

    def validate_quantity_delta(self, value):
        if value == 0:
            raise serializers.ValidationError(
                "Adjustment quantity cannot be zero."
            )
        return value

    def validate_reason(self, value):
        if not value:
            raise serializers.ValidationError("A reason is required.")
        return value

    def validate(self, attrs):
        raw_key = self.context["request"].headers.get("Idempotency-Key")
        try:
            attrs["idempotency_key"] = UUID(raw_key)
        except (TypeError, ValueError, AttributeError) as exc:
            raise serializers.ValidationError(
                {"idempotency_key": "A valid Idempotency-Key header is required."}
            ) from exc
        return attrs


class StockAdjustmentDecisionSerializer(serializers.Serializer):
    review_note = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
    )


class StockAdjustmentReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockAdjustment
        fields = [
            "id",
            "branch",
            "product",
            "idempotency_key",
            "quantity_delta",
            "expected_stock_version",
            "reason",
            "status",
            "review_note",
            "requested_by",
            "reviewed_by",
            "created_at",
            "reviewed_at",
        ]


class SaleLineInputSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.none())
    quantity = ExactDecimalField(
        max_digits=16,
        decimal_places=3,
        min_value=Decimal("0"),
    )

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value


class SplitPaymentInputSerializer(serializers.Serializer):
    method = serializers.ChoiceField(
        choices=[Payment.Method.CASH, Payment.Method.MPESA]
    )
    amount = ExactDecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0"),
    )
    amount_tendered = ExactDecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0"),
        required=False,
        allow_null=True,
    )
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Payment amount must be positive.")
        return value

    def validate(self, attrs):
        if attrs["method"] == Payment.Method.CASH:
            tendered = attrs.get("amount_tendered")
            if tendered is None:
                tendered = attrs["amount"]
            if tendered < attrs["amount"]:
                raise serializers.ValidationError(
                    {"amount_tendered": "Cash tender must cover its allocation."}
                )
            attrs["amount_tendered"] = tendered
            if attrs.get("phone_number"):
                raise serializers.ValidationError(
                    {"phone_number": "Phone number is only valid for M-Pesa."}
                )
        else:
            if attrs.get("amount_tendered") is not None:
                raise serializers.ValidationError(
                    {"amount_tendered": "M-Pesa does not accept cash tender."}
                )
            if attrs["amount"] != attrs["amount"].to_integral_value():
                raise serializers.ValidationError(
                    {"amount": "M-Pesa amounts must be whole currency units."}
                )
        return attrs


class CheckoutSerializer(serializers.Serializer):
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.none())
    shift = serializers.PrimaryKeyRelatedField(queryset=Shift.objects.none())
    payment_method = serializers.ChoiceField(choices=Sale.PaymentMethod.choices)
    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.none(),
        required=False,
        allow_null=True,
    )
    payments = SplitPaymentInputSerializer(many=True, required=False)
    amount_tendered = ExactDecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0"),
        required=False,
        allow_null=True,
    )
    lines = SaleLineInputSerializer(many=True, allow_empty=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context["request"]
        organisation = request.active_organisation
        self.fields["branch"].queryset = Branch.objects.for_organisation(
            organisation
        ).filter(is_active=True)
        self.fields["shift"].queryset = Shift.objects.for_organisation(
            organisation
        )
        self.fields["customer"].queryset = Customer.objects.for_organisation(
            organisation
        ).filter(is_active=True)
        self.fields["lines"].child.fields["product"].queryset = (
            Product.objects.for_organisation(organisation).filter(is_active=True)
        )

    def validate_lines(self, lines):
        product_ids = [line["product"].pk for line in lines]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError(
                "Each product may appear only once per sale."
            )
        return lines

    def validate(self, attrs):
        request = self.context["request"]
        shift = attrs["shift"]
        if shift.cashier_id != request.user.pk:
            raise serializers.ValidationError(
                {"shift": "The shift must belong to the authenticated cashier."}
            )
        if shift.branch_id != attrs["branch"].pk:
            raise serializers.ValidationError(
                {"branch": "The branch must match the selected shift."}
            )
        method = attrs["payment_method"]
        payments = attrs.get("payments", [])
        if method == Sale.PaymentMethod.MPESA:
            if attrs.get("amount_tendered") is not None:
                raise serializers.ValidationError(
                    {
                        "amount_tendered": (
                            "Do not provide cash tendered for a pending M-Pesa sale."
                        )
                    }
                )
            if payments:
                raise serializers.ValidationError(
                    {"payments": "M-Pesa checkout does not accept split allocations."}
                )
        elif method == Sale.PaymentMethod.CASH:
            if payments:
                raise serializers.ValidationError(
                    {"payments": "Use split payment for multiple payment methods."}
                )
        elif method == Sale.PaymentMethod.SPLIT:
            if attrs.get("amount_tendered") is not None:
                raise serializers.ValidationError(
                    {"amount_tendered": "Set cash tender on each split payment."}
                )
            if len(payments) != 2 or {
                payment["method"] for payment in payments
            } != {Payment.Method.CASH, Payment.Method.MPESA}:
                raise serializers.ValidationError(
                    {"payments": "Split payment requires one cash and one M-Pesa amount."}
                )
        elif method == Sale.PaymentMethod.CREDIT:
            if attrs.get("customer") is None:
                raise serializers.ValidationError(
                    {"customer": "A customer is required for a credit sale."}
                )
            if attrs.get("amount_tendered") is not None or payments:
                raise serializers.ValidationError(
                    {"payments": "Credit sales do not accept immediate payment entries."}
                )

        raw_key = request.headers.get("Idempotency-Key")
        try:
            attrs["idempotency_key"] = UUID(raw_key)
        except (TypeError, ValueError, AttributeError) as exc:
            raise serializers.ValidationError(
                {"idempotency_key": "A valid Idempotency-Key header is required."}
            ) from exc
        return attrs


class CustomerSerializer(serializers.ModelSerializer):
    credit_balance = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            "id",
            "name",
            "phone_number",
            "email",
            "credit_limit",
            "credit_balance",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "credit_balance", "created_at"]

    def get_credit_balance(self, customer):
        from .services import customer_credit_balance

        return customer_credit_balance(
            organisation=self.context["request"].active_organisation,
            customer=customer,
        )

    def create(self, validated_data):
        validated_data["organisation"] = self.context[
            "request"
        ].active_organisation
        return super().create(validated_data)


class CollectionAllocationInputSerializer(serializers.Serializer):
    sale = serializers.PrimaryKeyRelatedField(queryset=Sale.objects.none())
    amount = ExactDecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0"),
    )

class CustomerCollectionSerializer(serializers.Serializer):
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.none())
    shift = serializers.PrimaryKeyRelatedField(queryset=Shift.objects.none())
    method = serializers.ChoiceField(choices=Payment.Method.choices)
    amount = ExactDecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0"),
    )
    phone_number = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
    )
    allocations = CollectionAllocationInputSerializer(many=True, allow_empty=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        organisation = self.context["request"].active_organisation
        self.fields["branch"].queryset = Branch.objects.for_organisation(
            organisation
        ).filter(is_active=True)
        self.fields["shift"].queryset = Shift.objects.for_organisation(
            organisation
        )
        self.fields["allocations"].child.fields["sale"].queryset = (
            Sale.objects.for_organisation(organisation)
            .filter(
                customer=self.context["customer"],
                payment_method=Sale.PaymentMethod.CREDIT,
                status=Sale.Status.POSTED,
            )
        )

    def validate(self, attrs):
        shift = attrs["shift"]
        if shift.branch_id != attrs["branch"].pk:
            raise serializers.ValidationError(
                {"branch": "The branch must match the selected shift."}
            )
        if sum(
            (line["amount"] for line in attrs["allocations"]),
            Decimal("0.00"),
        ) != attrs["amount"]:
            raise serializers.ValidationError(
                {"allocations": "Allocations must equal the payment amount."}
            )
        if attrs["method"] == Payment.Method.MPESA:
            if attrs["amount"] != attrs["amount"].to_integral_value():
                raise serializers.ValidationError(
                    {"amount": "M-Pesa amounts must be whole currency units."}
                )
            if not attrs.get("phone_number"):
                raise serializers.ValidationError(
                    {"phone_number": "A phone number is required for M-Pesa."}
                )
        elif attrs.get("phone_number"):
            raise serializers.ValidationError(
                {"phone_number": "Phone number is only valid for M-Pesa."}
            )
        raw_key = self.context["request"].headers.get("Idempotency-Key")
        try:
            attrs["idempotency_key"] = UUID(raw_key)
        except (TypeError, ValueError, AttributeError) as exc:
            raise serializers.ValidationError(
                {"idempotency_key": "A valid Idempotency-Key header is required."}
            ) from exc
        return attrs


class PaymentInitiateSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)


class SaleReturnLineInputSerializer(serializers.Serializer):
    sale_line = serializers.PrimaryKeyRelatedField(queryset=SaleLine.objects.none())
    quantity = ExactDecimalField(
        max_digits=16,
        decimal_places=3,
        min_value=Decimal("0"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        sale = self.context.get("sale")
        if sale is not None:
            self.fields["sale_line"].queryset = SaleLine.objects.for_organisation(
                sale.organisation
            ).filter(sale=sale)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Return quantity must be positive.")
        return value


class SaleReturnCreateSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255, trim_whitespace=True)
    lines = SaleReturnLineInputSerializer(many=True, allow_empty=False)
    refund_method = serializers.ChoiceField(
        choices=Refund.Method.choices,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        sale = self.context.get("sale")
        if sale is not None:
            self.fields["lines"].child.fields["sale_line"].queryset = (
                SaleLine.objects.for_organisation(sale.organisation).filter(
                    sale=sale
                )
            )

    def validate_lines(self, lines):
        line_ids = [line["sale_line"].pk for line in lines]
        if len(line_ids) != len(set(line_ids)):
            raise serializers.ValidationError(
                "Each original sale line may appear only once."
            )
        return lines

    def validate(self, attrs):
        raw_key = self.context["request"].headers.get("Idempotency-Key")
        try:
            attrs["idempotency_key"] = UUID(raw_key)
        except (TypeError, ValueError, AttributeError) as exc:
            raise serializers.ValidationError(
                {"idempotency_key": "A valid Idempotency-Key header is required."}
            ) from exc
        return attrs


class RefundCompleteSerializer(serializers.Serializer):
    payout_reference = serializers.CharField(max_length=100)

    def validate_payout_reference(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("A payout reference is required.")
        return value


class SaleLineReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleLine
        fields = [
            "id",
            "product",
            "product_name",
            "sku",
            "unit",
            "quantity",
            "unit_price",
            "unit_cost",
            "tax_rate",
            "line_subtotal",
            "tax_amount",
            "line_total",
        ]


class ReceiptReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Receipt
        fields = [
            "receipt_number",
            "status",
            "snapshot",
            "issued_at",
        ]


class PaymentAllocationReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentAllocation
        fields = ["sale", "amount"]


class PaymentReadSerializer(serializers.ModelSerializer):
    allocations = PaymentAllocationReadSerializer(many=True, read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "purpose",
            "method",
            "status",
            "amount",
            "initiation_started_at",
            "checkout_request_id",
            "provider_receipt",
            "confirmed_at",
            "allocations",
        ]


class SaleReadSerializer(serializers.ModelSerializer):
    lines = SaleLineReadSerializer(many=True, read_only=True)
    receipt = ReceiptReadSerializer(read_only=True)
    payments = PaymentReadSerializer(many=True, read_only=True)

    class Meta:
        model = Sale
        fields = [
            "id",
            "sale_number",
            "branch",
            "shift",
            "cashier",
            "customer",
            "payment_method",
            "status",
            "subtotal",
            "tax_total",
            "total",
            "credit_amount",
            "amount_tendered",
            "change_due",
            "created_at",
            "completed_at",
            "lines",
            "payments",
            "receipt",
        ]


class SaleReturnLineReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleReturnLine
        fields = ["sale_line", "quantity", "amount"]


class RefundReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = [
            "id",
            "method",
            "status",
            "amount",
            "payout_reference",
            "completed_at",
        ]


class SaleReturnReadSerializer(serializers.ModelSerializer):
    lines = SaleReturnLineReadSerializer(many=True, read_only=True)
    refund = RefundReadSerializer(read_only=True)

    class Meta:
        model = SaleReturn
        fields = [
            "id",
            "sale",
            "reason",
            "total_amount",
            "credit_reduction_amount",
            "refund_amount",
            "lines",
            "refund",
            "created_at",
        ]
