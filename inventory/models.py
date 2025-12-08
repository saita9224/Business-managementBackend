from django.db import models
from django.utils import timezone


class Product(models.Model):
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=200, blank=True, null=True)
    unit = models.CharField(max_length=50, default="kg")
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name

    @property
    def current_stock(self):
        """
        Calculates stock as:
        sum(IN movements) - sum(OUT movements)
        """
        ins = (
            self.movements.filter(movement_type="IN")
            .aggregate(total=models.Sum("quantity"))["total"]
            or 0
        )

        outs = (
            self.movements.filter(movement_type="OUT")
            .aggregate(total=models.Sum("quantity"))["total"]
            or 0
        )

        return ins - outs


class StockMovement(models.Model):
    """
    Unified stock movement history.
    Handles all IN and OUT transactions.
    """

    MOVEMENT_TYPES = (
        ("IN", "Incoming"),
        ("OUT", "Outgoing"),
    )

    REASONS = (
        ("PURCHASE", "Purchase"),
        ("RETURN", "Return"),
        ("ADJUSTMENT", "Adjustment"),
        ("SALE", "Sale"),
        ("COOKING", "Cooking"),
        ("DAMAGED", "Damaged"),
        ("LOST", "Lost"),
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="movements"
    )

    quantity = models.FloatField()
    movement_type = models.CharField(max_length=10, choices=MOVEMENT_TYPES)
    reason = models.CharField(max_length=20, choices=REASONS)

    # Link to expense if IN movement came from a purchase
    expense_item = models.ForeignKey(
        "expenses.ExpenseItem",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stock_movements"
    )

    # Optional grouping ID
    group_id = models.CharField(max_length=100, null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.product.name} - {self.movement_type} ({self.quantity})"
