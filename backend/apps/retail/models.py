from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from core.tenancy import TenantModel


class Category(TenantModel):
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "name"],
                name="uniq_category_name_org",
            )
        ]
        indexes = [
            models.Index(
                fields=["organisation", "is_active", "name"],
                name="category_org_active_idx",
            )
        ]
        ordering = ["name", "pk"]

    def __str__(self):
        return self.name


class Product(TenantModel):
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="products",
    )
    name = models.CharField(max_length=160)
    sku = models.CharField(max_length=64)
    barcode = models.CharField(max_length=128, blank=True)
    unit = models.CharField(max_length=24, default="each")
    selling_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    cost_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    reorder_level = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        default=0,
        validators=[MinValueValidator(0)],
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "sku"],
                name="uniq_product_sku_org",
            ),
            models.UniqueConstraint(
                fields=["organisation", "barcode"],
                condition=~models.Q(barcode=""),
                name="uniq_product_barcode_org",
            ),
            models.CheckConstraint(
                condition=models.Q(tax_rate__lte=100),
                name="product_tax_rate_max",
            ),
            models.CheckConstraint(
                condition=models.Q(selling_price__gte=0),
                name="product_sell_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(cost_price__gte=0),
                name="product_cost_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(reorder_level__gte=0),
                name="product_reorder_nonnegative",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organisation", "is_active", "name"],
                name="product_org_active_name_idx",
            ),
            models.Index(
                fields=["organisation", "sku"],
                name="product_org_sku_idx",
            ),
            models.Index(
                fields=["organisation", "barcode"],
                name="product_org_barcode_idx",
            ),
        ]
        ordering = ["name", "pk"]

    def clean(self):
        super().clean()
        if (
            self.category_id
            and self.organisation_id
            and self.category.organisation_id != self.organisation_id
        ):
            raise ValidationError(
                {"category": "The category must belong to this organisation."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.sku})"


class Supplier(TenantModel):
    name = models.CharField(max_length=150)
    contact_name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    address = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "name"],
                name="uniq_supplier_name_org",
            )
        ]
        indexes = [
            models.Index(
                fields=["organisation", "is_active", "name"],
                name="supplier_org_active_idx",
            )
        ]
        ordering = ["name", "pk"]

    def __str__(self):
        return self.name


class StockBalance(TenantModel):
    branch = models.ForeignKey(
        "organisations.Branch",
        on_delete=models.PROTECT,
        related_name="stock_balances",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="stock_balances",
    )
    quantity = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        default=0,
        validators=[MinValueValidator(0)],
    )
    average_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "branch", "product"],
                name="uniq_stock_balance_org",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0),
                name="stock_balance_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(average_cost__gte=0),
                name="stock_average_cost_nonnegative",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organisation", "branch", "product"],
                name="stock_org_branch_prod_idx",
            )
        ]

    def clean(self):
        super().clean()
        if self.branch_id and self.organisation_id:
            if self.branch.organisation_id != self.organisation_id:
                raise ValidationError(
                    {"branch": "The branch must belong to this organisation."}
                )
        if self.product_id and self.organisation_id:
            if self.product.organisation_id != self.organisation_id:
                raise ValidationError(
                    {"product": "The product must belong to this organisation."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Shift(TenantModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    branch = models.ForeignKey(
        "organisations.Branch",
        on_delete=models.PROTECT,
        related_name="retail_shifts",
    )
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="retail_shifts",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.OPEN,
    )
    opening_float = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    expected_cash = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    counted_cash = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    variance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "branch", "cashier"],
                condition=models.Q(status="open"),
                name="uniq_open_shift_cashier_branch",
            ),
            models.CheckConstraint(
                condition=models.Q(opening_float__gte=0),
                name="shift_opening_float_nonnegative",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organisation", "branch", "status"],
                name="shift_org_branch_status_idx",
            )
        ]
        ordering = ["-opened_at"]

    def clean(self):
        super().clean()
        if self.branch_id and self.organisation_id:
            if self.branch.organisation_id != self.organisation_id:
                raise ValidationError(
                    {"branch": "The branch must belong to this organisation."}
                )
        if self.status == self.Status.OPEN and self.closed_at is not None:
            raise ValidationError(
                {"closed_at": "An open shift cannot have a close time."}
            )
        if self.status == self.Status.CLOSED and self.closed_at is None:
            raise ValidationError(
                {"closed_at": "A closed shift must have a close time."}
            )
        reconciliation = (
            self.expected_cash,
            self.counted_cash,
            self.variance,
        )
        if any(value is not None for value in reconciliation):
            if any(value is None for value in reconciliation):
                raise ValidationError(
                    "Expected, counted, and variance cash must be recorded together."
                )
            if self.variance != self.counted_cash - self.expected_cash:
                raise ValidationError(
                    {"variance": "Variance must equal counted cash minus expected cash."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Expense(TenantModel):
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        MPESA = "mpesa", "M-Pesa"

    branch = models.ForeignKey(
        "organisations.Branch",
        on_delete=models.PROTECT,
        related_name="retail_expenses",
    )
    shift = models.ForeignKey(
        Shift,
        on_delete=models.PROTECT,
        related_name="expenses",
    )
    category = models.CharField(max_length=80)
    description = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    payment_method = models.CharField(
        max_length=10,
        choices=PaymentMethod.choices,
    )
    idempotency_key = models.UUIDField()
    request_fingerprint = models.CharField(max_length=64)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="retail_expenses",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "idempotency_key"],
                name="uniq_expense_idem_org",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="retail_expense_amount_positive",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organisation", "branch", "created_at"],
                name="expense_org_branch_date_idx",
            ),
            models.Index(
                fields=["organisation", "shift", "created_at"],
                name="expense_org_shift_date_idx",
            ),
        ]
        ordering = ["-created_at"]

    def clean(self):
        super().clean()
        if self.amount <= 0:
            raise ValidationError({"amount": "Expense amount must be positive."})
        if (
            self.branch.organisation_id != self.organisation_id
            or self.shift.organisation_id != self.organisation_id
            or self.shift.branch_id != self.branch_id
        ):
            raise ValidationError(
                "Expense branch and shift must belong to this organisation."
            )

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Expenses are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Expenses cannot be deleted.")


class Customer(TenantModel):
    name = models.CharField(max_length=160)
    phone_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    credit_limit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["organisation", "is_active", "name"],
                name="customer_org_active_name_idx",
            )
        ]
        ordering = ["name", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(credit_limit__gte=0),
                name="customer_credit_limit_nonnegative",
            )
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.credit_limit < 0:
            raise ValidationError(
                {"credit_limit": "Credit limit cannot be negative."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Sale(TenantModel):
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        MPESA = "mpesa", "M-Pesa"
        SPLIT = "split", "Split payment"
        CREDIT = "credit", "Customer credit"

    class Status(models.TextChoices):
        POSTED = "posted", "Posted"
        PENDING_PAYMENT = "pending_payment", "Pending payment"
        CANCELLED = "cancelled", "Cancelled"

    branch = models.ForeignKey(
        "organisations.Branch",
        on_delete=models.PROTECT,
        related_name="retail_sales",
    )
    shift = models.ForeignKey(
        Shift,
        on_delete=models.PROTECT,
        related_name="sales",
    )
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="retail_sales",
    )
    customer = models.ForeignKey(
        Customer,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="sales",
    )
    sale_number = models.CharField(max_length=40)
    idempotency_key = models.UUIDField()
    request_fingerprint = models.CharField(max_length=64)
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
    )
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    tax_total = models.DecimalField(max_digits=14, decimal_places=2)
    total = models.DecimalField(max_digits=14, decimal_places=2)
    credit_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )
    amount_tendered = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    change_due = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "idempotency_key"],
                name="uniq_sale_idempotency_org",
            ),
            models.UniqueConstraint(
                fields=["organisation", "sale_number"],
                name="uniq_sale_number_org",
            ),
            models.CheckConstraint(
                condition=models.Q(subtotal__gte=0),
                name="sale_subtotal_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(tax_total__gte=0),
                name="sale_tax_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(total__gte=0),
                name="sale_total_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(credit_amount__gte=0),
                name="sale_credit_amount_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(change_due__gte=0),
                name="sale_change_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(total=models.F("subtotal") + models.F("tax_total")),
                name="sale_total_matches_parts",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organisation", "branch", "created_at"],
                name="sale_org_branch_date_idx",
            ),
            models.Index(
                fields=["organisation", "shift", "status"],
                name="sale_org_shift_status_idx",
            ),
        ]
        ordering = ["-created_at"]

    def clean(self):
        super().clean()
        if self.branch_id and self.organisation_id:
            if self.branch.organisation_id != self.organisation_id:
                raise ValidationError(
                    {"branch": "The branch must belong to this organisation."}
                )
        if self.shift_id and self.organisation_id:
            if (
                self.shift.organisation_id != self.organisation_id
                or self.shift.branch_id != self.branch_id
                or self.shift.cashier_id != self.cashier_id
            ):
                raise ValidationError(
                    {"shift": "The shift must match this sale's tenant, branch, and cashier."}
                )
        if (
            self.customer_id
            and self.organisation_id
            and self.customer.organisation_id != self.organisation_id
        ):
            raise ValidationError(
                {"customer": "The customer must belong to this organisation."}
            )
        if self.payment_method == self.PaymentMethod.CASH:
            if (
                self.status != self.Status.POSTED
                or self.completed_at is None
                or self.amount_tendered is None
                or self.amount_tendered < self.total
                or self.change_due != self.amount_tendered - self.total
                or self.credit_amount != 0
            ):
                raise ValidationError(
                    {
                        "amount_tendered": (
                            "A posted cash sale must be fully tendered and balanced."
                        )
                    }
                )
        elif self.payment_method == self.PaymentMethod.MPESA:
            if (
                self.status == self.Status.PENDING_PAYMENT
                and (
                    self.amount_tendered is not None
                    or self.completed_at is not None
                )
            ):
                raise ValidationError(
                    {"status": "Pending M-Pesa sales cannot be marked paid."}
                )
            if self.status == self.Status.POSTED and self.completed_at is None:
                raise ValidationError(
                    {"status": "M-Pesa sales require verified payment to post."}
                )
            if self.status == self.Status.CANCELLED and (
                self.amount_tendered is not None
                or self.completed_at is not None
                or self.cancelled_at is None
            ):
                raise ValidationError(
                    {"status": "Cancelled M-Pesa sales require a cancellation time."}
                )
            if self.credit_amount != 0:
                raise ValidationError(
                    {"credit_amount": "M-Pesa payments cannot create credit."}
                )
        elif self.payment_method == self.PaymentMethod.SPLIT:
            if self.status == self.Status.POSTED and self.completed_at is None:
                raise ValidationError(
                    {"status": "Completed split sales require a completion time."}
                )
            if self.status == self.Status.PENDING_PAYMENT and self.completed_at is not None:
                raise ValidationError(
                    {"status": "Pending split sales cannot have a completion time."}
                )
            if self.credit_amount != 0:
                raise ValidationError(
                    {"credit_amount": "Split payments cannot create customer credit."}
                )
        elif self.payment_method == self.PaymentMethod.CREDIT:
            if (
                self.customer_id is None
                or self.status != self.Status.POSTED
                or self.completed_at is None
                or self.credit_amount != self.total
                or self.amount_tendered is not None
            ):
                raise ValidationError(
                    {"customer": "A credit sale requires a customer and full credit balance."}
                )

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            previous = type(self).objects.only("status").get(pk=self.pk)
            if previous.status != self.Status.PENDING_PAYMENT:
                raise ValidationError("Completed or cancelled sales are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Sales cannot be deleted.")


class SaleLine(TenantModel):
    sale = models.ForeignKey(
        Sale,
        on_delete=models.PROTECT,
        related_name="lines",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="sale_lines",
    )
    product_name = models.CharField(max_length=160)
    sku = models.CharField(max_length=64)
    unit = models.CharField(max_length=24)
    quantity = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        validators=[MinValueValidator(0)],
    )
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2)
    line_subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2)
    line_total = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "sale", "product"],
                name="uniq_sale_line_product_org",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="sale_line_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="sale_line_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_cost__gte=0),
                name="sale_line_cost_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(line_subtotal__gte=0),
                name="sale_line_subtotal_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(tax_amount__gte=0),
                name="sale_line_tax_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(line_total__gte=0),
                name="sale_line_total_nonnegative",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organisation", "sale"],
                name="saleline_org_sale_idx",
            ),
            models.Index(
                fields=["organisation", "product", "created_at"],
                name="saleline_org_product_date_idx",
            ),
        ]

    def clean(self):
        super().clean()
        if self.sale_id and self.organisation_id:
            if self.sale.organisation_id != self.organisation_id:
                raise ValidationError(
                    {"sale": "The sale must belong to this organisation."}
                )
        if self.product_id and self.organisation_id:
            if self.product.organisation_id != self.organisation_id:
                raise ValidationError(
                    {"product": "The product must belong to this organisation."}
                )

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Sale lines are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Sale lines cannot be deleted.")


class Receipt(TenantModel):
    class Status(models.TextChoices):
        ISSUED = "issued", "Issued"
        PENDING_PAYMENT = "pending_payment", "Pending payment"
        VOIDED = "voided", "Voided"

    sale = models.OneToOneField(
        Sale,
        on_delete=models.PROTECT,
        related_name="receipt",
    )
    receipt_number = models.CharField(max_length=40)
    status = models.CharField(max_length=20, choices=Status.choices)
    snapshot = models.JSONField()
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "receipt_number"],
                name="uniq_receipt_number_org",
            )
        ]
        indexes = [
            models.Index(
                fields=["organisation", "issued_at"],
                name="receipt_org_issued_idx",
            )
        ]
        ordering = ["-issued_at"]

    def clean(self):
        super().clean()
        if self.sale_id and self.organisation_id:
            if self.sale.organisation_id != self.organisation_id:
                raise ValidationError(
                    {"sale": "The sale must belong to this organisation."}
                )

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous is not None and not (
                previous.status == self.Status.PENDING_PAYMENT
                and self.status in (self.Status.ISSUED, self.Status.VOIDED)
                and previous.sale_id == self.sale_id
            ):
                raise ValidationError(
                    "Only pending receipts may be finalized."
                )
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Receipts cannot be deleted.")


class Payment(TenantModel):
    class Purpose(models.TextChoices):
        SALE = "sale", "Sale payment"
        COLLECTION = "collection", "Customer collection"

    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        MPESA = "mpesa", "M-Pesa"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        FAILED = "failed", "Failed"

    purpose = models.CharField(max_length=12, choices=Purpose.choices)
    method = models.CharField(max_length=10, choices=Method.choices)
    status = models.CharField(max_length=10, choices=Status.choices)
    sale = models.ForeignKey(
        Sale,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    customer = models.ForeignKey(
        Customer,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    branch = models.ForeignKey(
        "organisations.Branch",
        on_delete=models.PROTECT,
        related_name="retail_payments",
    )
    shift = models.ForeignKey(
        Shift,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    idempotency_key = models.UUIDField()
    request_fingerprint = models.CharField(max_length=64)
    phone_number = models.CharField(max_length=15, blank=True)
    merchant_request_id = models.CharField(max_length=100, blank=True)
    checkout_request_id = models.CharField(max_length=100, blank=True)
    provider_receipt = models.CharField(max_length=64, blank=True)
    initiation_started_at = models.DateTimeField(null=True, blank=True)
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="initiated_retail_payments",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "idempotency_key"],
                name="uniq_payment_idem_org",
            ),
            models.UniqueConstraint(
                fields=["method", "checkout_request_id"],
                condition=~models.Q(checkout_request_id=""),
                name="uniq_payment_provider_request",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="payment_amount_positive",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organisation", "customer", "status"],
                name="pay_org_cust_status_idx",
            ),
            models.Index(
                fields=["organisation", "sale", "status"],
                name="payment_org_sale_status_idx",
            ),
        ]

    def clean(self):
        super().clean()
        if self.amount <= 0:
            raise ValidationError({"amount": "Payment amount must be positive."})
        if self.sale_id:
            if (
                self.sale.organisation_id != self.organisation_id
                or self.sale.branch_id != self.branch_id
                or self.purpose != self.Purpose.SALE
                or self.customer_id != self.sale.customer_id
            ):
                raise ValidationError(
                    {"sale": "Payment references must match the sale tenant and customer."}
                )
        elif self.purpose != self.Purpose.COLLECTION or self.customer_id is None:
            raise ValidationError(
                {"customer": "Customer collection payments require a customer."}
            )
        if (
            self.customer_id
            and self.customer.organisation_id != self.organisation_id
        ):
            raise ValidationError(
                {"customer": "The customer must belong to this organisation."}
            )
        if self.branch.organisation_id != self.organisation_id:
            raise ValidationError(
                {"branch": "The branch must belong to this organisation."}
            )
        if self.shift_id and (
            self.shift.organisation_id != self.organisation_id
            or self.shift.branch_id != self.branch_id
        ):
            raise ValidationError(
                {"shift": "The shift must match the payment tenant and branch."}
            )
        if self.method == self.Method.MPESA and not self.phone_number:
            if self.status == self.Status.PENDING and self.checkout_request_id:
                raise ValidationError(
                    {"phone_number": "M-Pesa payment requires a phone number."}
                )
        if self.status == self.Status.CONFIRMED and self.confirmed_at is None:
            raise ValidationError(
                {"confirmed_at": "Confirmed payments require a confirmation time."}
            )

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous and previous.status != self.Status.PENDING:
                raise ValidationError("Confirmed and failed payments are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)


class PaymentAllocation(TenantModel):
    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    sale = models.ForeignKey(
        Sale,
        on_delete=models.PROTECT,
        related_name="payment_allocations",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "payment", "sale"],
                name="uniq_payment_sale_allocation",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="payment_allocation_positive",
            ),
        ]

    def clean(self):
        super().clean()
        if self.amount <= 0:
            raise ValidationError({"amount": "Allocation must be positive."})
        if (
            self.payment.organisation_id != self.organisation_id
            or self.sale.organisation_id != self.organisation_id
        ):
            raise ValidationError(
                "Payment allocation references must belong to this organisation."
            )
        if self.payment.sale_id and self.payment.sale_id != self.sale_id:
            raise ValidationError(
                {"sale": "Sale payments can only be allocated to their own sale."}
            )
        if self.payment.customer_id != self.sale.customer_id:
            raise ValidationError(
                {"sale": "Payment and sale must belong to the same customer."}
            )
        if self.payment.branch_id != self.sale.branch_id:
            raise ValidationError(
                {"sale": "Payment and sale must belong to the same branch."}
            )

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Payment allocations are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Payment allocations cannot be deleted.")


class MpesaProviderEvent(TenantModel):
    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        PROCESSED = "processed", "Processed"
        REJECTED = "rejected", "Rejected"

    event_id = models.CharField(max_length=100)
    payment = models.ForeignKey(
        Payment,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="provider_events",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.RECEIVED,
    )
    result_code = models.CharField(max_length=16)
    payload_fingerprint = models.CharField(max_length=64)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "event_id"],
                name="uniq_mpesa_event_org",
            )
        ]

    def clean(self):
        super().clean()
        if (
            self.payment_id
            and self.payment.organisation_id != self.organisation_id
        ):
            raise ValidationError(
                {"payment": "Provider event payment must belong to this organisation."}
            )

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous and not (
                previous.status == self.Status.RECEIVED
                and self.status in (self.Status.PROCESSED, self.Status.REJECTED)
            ):
                raise ValidationError("Processed provider events are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)


class SaleReturn(TenantModel):
    sale = models.ForeignKey(
        Sale,
        on_delete=models.PROTECT,
        related_name="returns",
    )
    branch = models.ForeignKey(
        "organisations.Branch",
        on_delete=models.PROTECT,
        related_name="retail_returns",
    )
    idempotency_key = models.UUIDField()
    request_fingerprint = models.CharField(max_length=64)
    reason = models.CharField(max_length=255)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    credit_reduction_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )
    refund_amount = models.DecimalField(max_digits=14, decimal_places=2)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="retail_returns",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "idempotency_key"],
                name="uniq_return_idem_org",
            ),
            models.CheckConstraint(
                condition=models.Q(total_amount__gt=0),
                name="sale_return_total_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(credit_reduction_amount__gte=0),
                name="sale_return_credit_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(refund_amount__gte=0),
                name="sale_return_refund_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    credit_reduction_amount=models.F("total_amount")
                    - models.F("refund_amount")
                ),
                name="sale_return_amounts_match",
            ),
        ]

    def clean(self):
        super().clean()
        if (
            self.sale.organisation_id != self.organisation_id
            or self.sale.branch_id != self.branch_id
            or self.branch.organisation_id != self.organisation_id
        ):
            raise ValidationError(
                "Return references must match the sale tenant and branch."
            )
        if (
            self.credit_reduction_amount + self.refund_amount
            != self.total_amount
        ):
            raise ValidationError(
                "Credit reduction and refund must equal the return total."
            )

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Returns are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Returns cannot be deleted.")


class SaleReturnLine(TenantModel):
    sale_return = models.ForeignKey(
        SaleReturn,
        on_delete=models.PROTECT,
        related_name="lines",
    )
    sale_line = models.ForeignKey(
        SaleLine,
        on_delete=models.PROTECT,
        related_name="return_lines",
    )
    quantity = models.DecimalField(max_digits=16, decimal_places=3)
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "sale_return", "sale_line"],
                name="uniq_return_line_org",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="sale_return_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="sale_return_line_amount_positive",
            ),
        ]

    def clean(self):
        super().clean()
        if (
            self.sale_return.organisation_id != self.organisation_id
            or self.sale_line.organisation_id != self.organisation_id
            or self.sale_return.sale_id != self.sale_line.sale_id
        ):
            raise ValidationError(
                "Return line and original sale line references must match."
            )

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Return lines are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Return lines cannot be deleted.")


class Refund(TenantModel):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        MPESA = "mpesa", "M-Pesa"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending payout"
        COMPLETED = "completed", "Completed"

    sale_return = models.OneToOneField(
        SaleReturn,
        on_delete=models.PROTECT,
        related_name="refund",
    )
    shift = models.ForeignKey(
        Shift,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="refunds",
    )
    method = models.CharField(max_length=10, choices=Method.choices)
    status = models.CharField(max_length=10, choices=Status.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payout_reference = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="retail_refunds",
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="refund_amount_positive",
            )
        ]

    @property
    def branch(self):
        return self.sale_return.branch

    def clean(self):
        super().clean()
        if (
            self.sale_return.organisation_id != self.organisation_id
            or self.amount != self.sale_return.refund_amount
        ):
            raise ValidationError(
                "Refund must match its return tenant and remaining refund amount."
            )
        if self.shift_id and (
            self.shift.organisation_id != self.organisation_id
            or self.shift.branch_id != self.sale_return.branch_id
        ):
            raise ValidationError(
                {"shift": "Refund shift must match the return tenant and branch."}
            )
        if self.method == self.Method.CASH and self.status != self.Status.COMPLETED:
            raise ValidationError({"status": "Cash refunds complete immediately."})
        if self.method == self.Method.CASH and self.completed_at is None:
            raise ValidationError(
                {"completed_at": "Cash refunds require a completion time."}
            )
        if self.method == self.Method.MPESA and self.status == self.Status.COMPLETED:
            if self.completed_at is None or not self.payout_reference:
                raise ValidationError(
                    {"payout_reference": "Completed M-Pesa refunds require a payout reference."}
                )

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous and previous.status != self.Status.PENDING:
                raise ValidationError("Completed refunds are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)


class GoodsReceipt(TenantModel):
    class Status(models.TextChoices):
        POSTED = "posted", "Posted"

    branch = models.ForeignKey(
        "organisations.Branch",
        on_delete=models.PROTECT,
        related_name="goods_receipts",
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="goods_receipts",
    )
    idempotency_key = models.UUIDField()
    request_fingerprint = models.CharField(max_length=64)
    supplier_reference = models.CharField(max_length=100, blank=True)
    total_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.POSTED,
    )
    received_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="created_goods_receipts",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "idempotency_key"],
                name="uniq_goods_receipt_idem_org",
            ),
            models.CheckConstraint(
                condition=models.Q(total_cost__gte=0),
                name="goods_receipt_total_nonnegative",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organisation", "branch", "received_at"],
                name="receipt_org_branch_date_idx",
            ),
            models.Index(
                fields=["organisation", "supplier", "received_at"],
                name="receipt_org_supplier_idx",
            ),
        ]
        ordering = ["-received_at"]

    def clean(self):
        super().clean()
        if self.branch_id and self.organisation_id:
            if self.branch.organisation_id != self.organisation_id:
                raise ValidationError(
                    {"branch": "The branch must belong to this organisation."}
                )
        if self.supplier_id and self.organisation_id:
            if self.supplier.organisation_id != self.organisation_id:
                raise ValidationError(
                    {"supplier": "The supplier must belong to this organisation."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class GoodsReceiptLine(TenantModel):
    receipt = models.ForeignKey(
        GoodsReceipt,
        on_delete=models.PROTECT,
        related_name="lines",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="goods_receipt_lines",
    )
    quantity = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        validators=[MinValueValidator(0)],
    )
    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    line_total = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "receipt", "product"],
                name="uniq_receipt_product_org",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="receipt_line_qty_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_cost__gte=0),
                name="receipt_line_cost_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(line_total__gte=0),
                name="receipt_line_total_nonnegative",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organisation", "receipt"],
                name="receiptline_org_receipt_idx",
            )
        ]

    def clean(self):
        super().clean()
        if self.receipt_id and self.organisation_id:
            if self.receipt.organisation_id != self.organisation_id:
                raise ValidationError(
                    {"receipt": "The receipt must belong to this organisation."}
                )
        if self.product_id and self.organisation_id:
            if self.product.organisation_id != self.organisation_id:
                raise ValidationError(
                    {"product": "The product must belong to this organisation."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class StockAdjustment(TenantModel):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    branch = models.ForeignKey(
        "organisations.Branch",
        on_delete=models.PROTECT,
        related_name="stock_adjustments",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="stock_adjustments",
    )
    idempotency_key = models.UUIDField()
    request_fingerprint = models.CharField(max_length=64)
    quantity_delta = models.DecimalField(max_digits=16, decimal_places=3)
    expected_stock_version = models.PositiveBigIntegerField()
    reason = models.CharField(max_length=255)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.REQUESTED,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requested_stock_adjustments",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reviewed_stock_adjustments",
    )
    review_note = models.CharField(max_length=255, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "idempotency_key"],
                name="uniq_stock_adjustment_idem",
            ),
            models.CheckConstraint(
                condition=~models.Q(quantity_delta=0),
                name="stock_adjustment_delta_nonzero",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organisation", "status", "created_at"],
                name="adjustment_org_status_idx",
            ),
            models.Index(
                fields=["organisation", "branch", "product"],
                name="adjustment_org_branch_prod_idx",
            ),
        ]
        ordering = ["-created_at"]

    def clean(self):
        super().clean()
        if self.branch_id and self.organisation_id:
            if self.branch.organisation_id != self.organisation_id:
                raise ValidationError(
                    {"branch": "The branch must belong to this organisation."}
                )
        if self.product_id and self.organisation_id:
            if self.product.organisation_id != self.organisation_id:
                raise ValidationError(
                    {"product": "The product must belong to this organisation."}
                )
        if self.quantity_delta == 0:
            raise ValidationError(
                {"quantity_delta": "Adjustment quantity cannot be zero."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class StockMovement(TenantModel):
    class MovementType(models.TextChoices):
        RECEIPT = "receipt", "Goods receipt"
        ADJUSTMENT = "adjustment", "Stock adjustment"
        SALE = "sale", "Sale"
        RETURN = "return", "Return"
        SALE_REVERSAL = "sale_reversal", "Failed sale reversal"

    branch = models.ForeignKey(
        "organisations.Branch",
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    movement_type = models.CharField(max_length=16, choices=MovementType.choices)
    quantity_delta = models.DecimalField(max_digits=16, decimal_places=3)
    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    goods_receipt = models.ForeignKey(
        GoodsReceipt,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    stock_adjustment = models.ForeignKey(
        StockAdjustment,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    sale = models.ForeignKey(
        Sale,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    sale_return_line = models.ForeignKey(
        "retail.SaleReturnLine",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    payment = models.ForeignKey(
        Payment,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="stock_movements",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(quantity_delta=0),
                name="stock_movement_delta_nonzero",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_cost__gte=0),
                name="stock_movement_cost_nonnegative",
            ),
            models.UniqueConstraint(
                fields=["organisation", "sale", "product"],
                condition=models.Q(movement_type="sale_reversal"),
                name="uniq_failed_sale_reversal",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organisation", "branch", "product", "created_at"],
                name="movement_org_branch_prod_idx",
            ),
            models.Index(
                fields=["organisation", "movement_type", "created_at"],
                name="movement_org_type_date_idx",
            ),
        ]
        ordering = ["-created_at"]

    def clean(self):
        super().clean()
        if self.branch_id and self.organisation_id:
            if self.branch.organisation_id != self.organisation_id:
                raise ValidationError(
                    {"branch": "The branch must belong to this organisation."}
                )
        if self.product_id and self.organisation_id:
            if self.product.organisation_id != self.organisation_id:
                raise ValidationError(
                    {"product": "The product must belong to this organisation."}
                )
        if self.movement_type == self.MovementType.RECEIPT:
            if (
                not self.goods_receipt_id
                or self.stock_adjustment_id
                or self.sale_id
                or self.sale_return_line_id
                or self.payment_id
            ):
                raise ValidationError(
                    "A receipt movement must reference one goods receipt."
                )
            if (
                self.goods_receipt.organisation_id != self.organisation_id
                or self.goods_receipt.branch_id != self.branch_id
            ):
                raise ValidationError(
                    {"goods_receipt": "Receipt movement references must match."}
                )
            if not self.goods_receipt.lines.filter(product_id=self.product_id).exists():
                raise ValidationError(
                    {"product": "The product must be included on the receipt."}
                )
            if self.quantity_delta <= 0:
                raise ValidationError(
                    {"quantity_delta": "Receipt movement quantity must be positive."}
                )
        elif self.movement_type == self.MovementType.ADJUSTMENT:
            if (
                not self.stock_adjustment_id
                or self.goods_receipt_id
                or self.sale_id
                or self.sale_return_line_id
                or self.payment_id
            ):
                raise ValidationError(
                    "An adjustment movement must reference one stock adjustment."
                )
            if (
                self.stock_adjustment.organisation_id != self.organisation_id
                or self.stock_adjustment.branch_id != self.branch_id
                or self.stock_adjustment.product_id != self.product_id
                or self.stock_adjustment.quantity_delta != self.quantity_delta
            ):
                raise ValidationError(
                    {
                        "stock_adjustment": (
                            "Adjustment movement references must match."
                        )
                    }
                )
        elif self.movement_type == self.MovementType.SALE:
            if (
                not self.sale_id
                or self.goods_receipt_id
                or self.stock_adjustment_id
                or self.sale_return_line_id
                or self.payment_id
            ):
                raise ValidationError("A sale movement must reference one sale.")
            if (
                self.sale.organisation_id != self.organisation_id
                or self.sale.branch_id != self.branch_id
            ):
                raise ValidationError(
                    {"sale": "Sale movement references must match."}
                )
            if not self.sale.lines.filter(product_id=self.product_id).exists():
                raise ValidationError(
                    {"product": "The product must be included on the sale."}
                )
            if self.quantity_delta >= 0:
                raise ValidationError(
                    {"quantity_delta": "Sale movement quantity must be negative."}
                )
        elif self.movement_type == self.MovementType.SALE_REVERSAL:
            if (
                not self.sale_id
                or not self.payment_id
                or self.goods_receipt_id
                or self.stock_adjustment_id
                or self.sale_return_line_id
            ):
                raise ValidationError(
                    "A failed sale reversal must reference its sale and payment."
                )
            if (
                self.sale.organisation_id != self.organisation_id
                or self.sale.branch_id != self.branch_id
                or self.sale.status != Sale.Status.CANCELLED
                or self.payment.organisation_id != self.organisation_id
                or self.payment.sale_id != self.sale_id
                or self.payment.status != Payment.Status.FAILED
                or self.payment.method != Payment.Method.MPESA
            ):
                raise ValidationError(
                    {"payment": "Reversal references must match a failed M-Pesa sale."}
                )
            if not self.sale.lines.filter(product_id=self.product_id).exists():
                raise ValidationError(
                    {"product": "The product must be included on the sale."}
                )
            if self.quantity_delta <= 0:
                raise ValidationError(
                    {"quantity_delta": "Sale reversal quantity must be positive."}
                )
        elif self.movement_type == self.MovementType.RETURN:
            if (
                not self.sale_return_line_id
                or self.goods_receipt_id
                or self.stock_adjustment_id
                or self.sale_id
                or self.payment_id
            ):
                raise ValidationError(
                    "A return movement must reference one sale return line."
                )
            return_line = self.sale_return_line
            if (
                return_line.organisation_id != self.organisation_id
                or return_line.sale_return.branch_id != self.branch_id
                or return_line.sale_line.product_id != self.product_id
                or return_line.quantity != self.quantity_delta
            ):
                raise ValidationError(
                    {"sale_return_line": "Return movement references must match."}
                )
            if self.quantity_delta <= 0:
                raise ValidationError(
                    {"quantity_delta": "Return movement quantity must be positive."}
                )
        elif (
            self.goods_receipt_id
            or self.stock_adjustment_id
            or self.sale_id
            or self.sale_return_line_id
            or self.payment_id
        ):
            raise ValidationError("Stock movement references must match its type.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
