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

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Sale(TenantModel):
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        MPESA = "mpesa", "M-Pesa"

    class Status(models.TextChoices):
        POSTED = "posted", "Posted"
        PENDING_PAYMENT = "pending_payment", "Pending payment"

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
    amount_tendered = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    change_due = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    completed_at = models.DateTimeField(null=True, blank=True)

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
        if self.payment_method == self.PaymentMethod.CASH:
            if (
                self.status != self.Status.POSTED
                or self.completed_at is None
                or self.amount_tendered is None
                or self.amount_tendered < self.total
                or self.change_due != self.amount_tendered - self.total
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
            if self.status == self.Status.POSTED and (
                self.amount_tendered is None
                or self.amount_tendered < self.total
                or self.completed_at is None
            ):
                raise ValidationError(
                    {"status": "M-Pesa sales require verified payment to post."}
                )

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            previous = type(self).objects.only("status").get(pk=self.pk)
            if previous.status == self.Status.POSTED:
                raise ValidationError("Posted sales are immutable.")
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
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Receipts are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Receipts cannot be deleted.")


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
    movement_type = models.CharField(max_length=12, choices=MovementType.choices)
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
            if not self.goods_receipt_id or self.stock_adjustment_id:
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
            if not self.stock_adjustment_id or self.goods_receipt_id:
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
        elif self.goods_receipt_id or self.stock_adjustment_id or self.sale_id:
            raise ValidationError(
                "Return movements cannot reference receipt, adjustment, or sale records."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
