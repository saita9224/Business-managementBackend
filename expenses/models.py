# expenses/models.py

import uuid
import logging
from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum, Q
from django.db.models.constraints import CheckConstraint

logger = logging.getLogger(__name__)


# --------------------------------------------------
# SUPPLIER
# --------------------------------------------------

class Supplier(models.Model):
    name = models.CharField(max_length=255, unique=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return self.name


# --------------------------------------------------
# EXPENSE ITEM
# --------------------------------------------------

class ExpenseItem(models.Model):

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        related_name="expenses"
    )

    product = models.ForeignKey(
        "inventory.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expense_items",
    )

    item_name = models.CharField(max_length=255)

    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    total_price = models.DecimalField(
        max_digits=14,
        decimal_places=2
    )

    payment_group_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        db_index=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(fields=["supplier"]),
            models.Index(fields=["product"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["payment_group_id"]),
        ]

        constraints = [

            # Quantity must be > 0
            CheckConstraint(
                check=Q(quantity__gt=0),
                name="expense_quantity_gt_zero"
            ),

            # Unit price must be > 0
            CheckConstraint(
                check=Q(unit_price__gt=0),
                name="expense_unit_price_gt_zero"
            ),

            # Total price must be >= 0
            CheckConstraint(
                check=Q(total_price__gte=0),
                name="expense_total_price_non_negative"
            ),
        ]

    def __str__(self):
        supplier_name = self.supplier.name if self.supplier else "No Supplier"
        return f"{self.item_name} - {supplier_name}"

    def clean(self):

        from .utils import to_decimal

        quantity = to_decimal(self.quantity, "Quantity")
        unit_price = to_decimal(self.unit_price, "Unit price")

        if quantity <= 0:
            raise ValidationError({"quantity": "Must be greater than zero."})

        if unit_price <= 0:
            raise ValidationError({"unit_price": "Must be greater than zero."})

        if not self.payment_group_id:
            raise ValidationError("payment_group_id must not be empty.")

        self.total_price = (quantity * unit_price).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# --------------------------------------------------
# EXPENSE PAYMENT
# --------------------------------------------------

class ExpensePayment(models.Model):

    expense = models.ForeignKey(
        ExpenseItem,
        on_delete=models.CASCADE,
        related_name="payments"
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    paid_at = models.DateTimeField(
        default=timezone.now
    )

    class Meta:
        ordering = ["-paid_at"]

        indexes = [
            models.Index(fields=["expense"]),
            models.Index(fields=["paid_at"]),
        ]

        constraints = [

            # Payment must be positive
            CheckConstraint(
                check=Q(amount__gt=0),
                name="payment_amount_gt_zero"
            )
        ]

    def __str__(self):
        return f"Payment {self.amount} for {self.expense}"

    def clean(self):

        amount_dec = Decimal(str(self.amount))

        if amount_dec <= Decimal("0.00"):
            raise ValidationError("Payment amount must be greater than zero.")

        qs = ExpensePayment.objects.filter(expense=self.expense)

        if self.pk:
            qs = qs.exclude(pk=self.pk)

        agg = qs.aggregate(total=Sum("amount"))

        paid_so_far = agg.get("total") or Decimal("0.00")

        paid_so_far = Decimal(str(paid_so_far))

        new_total = paid_so_far + amount_dec

        if new_total > Decimal(self.expense.total_price):
            raise ValidationError(
                "Payment exceeds total price of the expense item."
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)