# inventory/models.py

from django.db import models
from django.db.models import Q, Value, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError


# ======================================================
# CATEGORY
# ======================================================

class Category(models.Model):
    client_id  = models.UUIDField(null=True, blank=True, unique=True, db_index=True)
    name       = models.CharField(max_length=100, unique=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# ======================================================
# PRODUCT
# ======================================================

class Product(models.Model):
    client_id = models.UUIDField(null=True, blank=True, unique=True, db_index=True)
    name     = models.CharField(max_length=200, unique=True)
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="products",
    )
    unit = models.CharField(max_length=50, default="kg")
    # -----------------------------------------------------------------
    # Finance related fields
    # -----------------------------------------------------------------
    # Cost per unit for the product – required for accurate profit calculations.
    # Stored as Decimal with 2 decimal places (currency). Must be > 0.
    cost_per_unit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cost of a single unit of the product. Used for COGS.",
    )
    # Flag used for legacy data migration – true when the cost was generated
    # automatically from historic averages.
    cost_generated = models.BooleanField(default=False)

    auto_deduct_on_sale = models.BooleanField(
        default=False,
        help_text=(
            "If True, POS sales automatically create OUT stock movements. "
            "Set True only for products sold directly through the POS counter. "
            "Leave False for raw ingredients, cooking supplies, etc."
        ),
    )

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return self.name

    @property
    def current_stock(self):
        # Single aggregate query — previously ran two separate
        # SUM queries (one for IN, one for OUT), which multiplied
        # into N+1 anywhere current_stock is read in a loop.
        agg = self.movements.aggregate(
            ins=Coalesce(
                models.Sum("quantity", filter=Q(movement_type=StockMovement.IN)),
                Value(0), output_field=DecimalField(),
            ),
            outs=Coalesce(
                models.Sum("quantity", filter=Q(movement_type=StockMovement.OUT)),
                Value(0), output_field=DecimalField(),
            ),
        )
        return agg["ins"] - agg["outs"]


# ======================================================
# PRODUCT PACKAGING (unit-of-measure conversions)
# ======================================================
#
# Product.unit is the canonical BASE unit — every StockMovement
# quantity is stored in base units. A ProductPackaging row says
# "1 <label> = quantity_in_base <base units>", e.g. for flour with
# base unit "kg":  bale -> 24,  packet 2kg -> 2.
# Purchase/sale entry points accept a packaging label and convert
# to base units before touching stock.

class ProductPackaging(models.Model):
    client_id = models.UUIDField(
        null=True, blank=True, unique=True, db_index=True
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="packagings",
    )
    label = models.CharField(
        max_length=100,
        help_text="Display name, e.g. 'bale', 'packet 2kg'. Matched case-insensitively.",
    )
    quantity_in_base = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        help_text="How many base units (Product.unit) one of this packaging contains.",
    )
    is_purchase_unit = models.BooleanField(
        default=False,
        help_text="Shown as an option when recording purchases/stock IN.",
    )
    is_sale_unit = models.BooleanField(
        default=False,
        help_text="Shown as an option when recording sales/stock OUT.",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["label"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "label"],
                name="unique_product_packaging_label",
            ),
        ]

    def __str__(self):
        return f"{self.product.name} | {self.label} = {self.quantity_in_base} {self.product.unit}"


# ======================================================
# STOCK MOVEMENT
# ======================================================

class StockMovement(models.Model):
    IN  = "IN"
    OUT = "OUT"

    MOVEMENT_TYPES = (
        (IN,  "Incoming"),
        (OUT, "Outgoing"),
    )

    PURCHASE   = "PURCHASE"
    RETURN     = "RETURN"
    ADJUSTMENT = "ADJUSTMENT"
    SALE       = "SALE"
    COOKING    = "COOKING"
    DAMAGED    = "DAMAGED"
    LOST       = "LOST"

    REASONS = (
        (PURCHASE,   "Purchase"),
        (RETURN,     "Return"),
        (ADJUSTMENT, "Adjustment"),
        (SALE,       "Sale"),
        (COOKING,    "Cooking"),
        (DAMAGED,    "Damaged"),
        (LOST,       "Lost"),
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="movements",
    )
    quantity = models.DecimalField(
        max_digits=12, decimal_places=3,
        help_text="Always positive. Direction via movement_type.",
    )
    movement_type = models.CharField(max_length=10, choices=MOVEMENT_TYPES)
    reason        = models.CharField(max_length=20, choices=REASONS)

    expense_item = models.ForeignKey(
        "expenses.ExpenseItem",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="stock_movements",
    )
    funded_by_business = models.BooleanField(
        default=True,
        help_text="False if stock was acquired using personal/outside cash",
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="stock_movements",
    )
    group_id = models.CharField(max_length=100, null=True, blank=True)
    client_id = models.UUIDField(
        null=True, blank=True, unique=True, db_index=True
    )

    receipt = models.ForeignKey(
        "POS.Receipt",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="inventory_movements",
    )
    order_item_id = models.BigIntegerField(
        null=True, blank=True,
        help_text="OrderItem ID that caused this movement (POS audit)",
    )

    notes      = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product", "movement_type"]),
            models.Index(fields=["reason"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["group_id"]),
        ]

    def clean(self):
        if self.quantity <= 0:
            raise ValidationError("Quantity must be greater than zero.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        Product.objects.filter(pk=self.product_id).update(updated_at=timezone.now())

    def __str__(self):
        return f"{self.product.name} | {self.movement_type} | {self.quantity}"


# ======================================================
# STOCK RECONCILIATION
# ======================================================

class StockReconciliation(models.Model):
    PENDING  = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

    STATUSES = (
        (PENDING,  "Pending"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="reconciliations",
    )
    counted_quantity = models.FloatField(help_text="Physically counted stock")
    system_quantity  = models.FloatField(help_text="System stock at time of count")
    difference       = models.FloatField(help_text="counted_quantity - system_quantity")

    status = models.CharField(
        max_length=20, choices=STATUSES, default=PENDING,
    )
    counted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name="stock_counts",
    )
    counted_at  = models.DateTimeField(default=timezone.now)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_reconciliations",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    notes       = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-counted_at"]
        indexes = [
            models.Index(fields=["product", "status"]),
            models.Index(fields=["counted_at"]),
        ]

    def __str__(self):
        return (
            f"{self.product.name} | "
            f"Counted: {self.counted_quantity} | "
            f"Diff: {self.difference} | "
            f"{self.status}"
        )
