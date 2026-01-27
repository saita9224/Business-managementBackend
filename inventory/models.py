from django.db import models
from django.utils import timezone
from django.conf import settings


class Product(models.Model):
    """
    Inventory product.
    Stock is NEVER stored directly.
    Derived strictly from StockMovement.
    """
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=200, blank=True, null=True)
    unit = models.CharField(max_length=50, default="kg")
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name

    @property
    def current_stock(self) -> float:
        """
        Stock = total IN - total OUT
        """
        ins = (
            self.movements.filter(movement_type=StockMovement.IN)
            .aggregate(total=models.Sum("quantity"))["total"]
            or 0
        )

        outs = (
            self.movements.filter(movement_type=StockMovement.OUT)
            .aggregate(total=models.Sum("quantity"))["total"]
            or 0
        )

        return ins - outs


class StockMovement(models.Model):
    """
    Unified stock movement log.
    SINGLE SOURCE OF TRUTH for inventory.
    """

    # ---- Movement direction ----
    IN = "IN"
    OUT = "OUT"

    MOVEMENT_TYPES = (
        (IN, "Incoming"),
        (OUT, "Outgoing"),
    )

    # ---- Business reasons ----
    PURCHASE = "PURCHASE"
    RETURN = "RETURN"
    ADJUSTMENT = "ADJUSTMENT"
    SALE = "SALE"
    COOKING = "COOKING"
    DAMAGED = "DAMAGED"
    LOST = "LOST"

    REASONS = (
        (PURCHASE, "Purchase"),
        (RETURN, "Return"),
        (ADJUSTMENT, "Adjustment"),
        (SALE, "Sale"),
        (COOKING, "Cooking"),
        (DAMAGED, "Damaged"),
        (LOST, "Lost"),
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="movements"
    )

    quantity = models.FloatField()
    movement_type = models.CharField(max_length=10, choices=MOVEMENT_TYPES)
    reason = models.CharField(max_length=20, choices=REASONS)

    # Optional expense link (ONLY for business-funded purchases)
    expense_item = models.ForeignKey(
        "expenses.ExpenseItem",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stock_movements"
    )

    # Who funded the stock
    funded_by_business = models.BooleanField(
        default=True,
        help_text="False if stock was acquired using personal/outside cash"
    )

    # Who performed the action (AUDIT CRITICAL)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stock_movements"
    )

    # Optional grouping (bulk purchase, cooking batch, reconciliation session)
    group_id = models.CharField(max_length=100, null=True, blank=True)

    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.product.name} | {self.movement_type} | {self.quantity}"


class StockReconciliation(models.Model):
    """
    Temporary storage for physical stock counts.
    NOT a source of truth.
    Must be approved to affect StockMovement.
    """

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

    STATUSES = (
        (PENDING, "Pending"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="reconciliations"
    )

    counted_quantity = models.FloatField(
        help_text="Physically counted stock"
    )

    system_quantity = models.FloatField(
        help_text="System-calculated stock at time of count"
    )

    difference = models.FloatField(
        help_text="counted_quantity - system_quantity"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUSES,
        default=PENDING
    )

    # Who performed the physical count
    counted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="stock_counts"
    )

    counted_at = models.DateTimeField(default=timezone.now)

    # Approval audit
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_reconciliations"
    )

    approved_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return (
            f"{self.product.name} | "
            f"Counted: {self.counted_quantity} | "
            f"Diff: {self.difference} | "
            f"{self.status}"
        )
