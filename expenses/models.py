# expenses/models.py
import uuid
import logging
from decimal import Decimal, ROUND_HALF_UP
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum

logger = logging.getLogger(__name__)


class Supplier(models.Model):
    name = models.CharField(max_length=255, unique=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class ExpenseItem(models.Model):
    supplier = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL, null=True, related_name="expenses"
    )

    product = models.ForeignKey(
        "inventory.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expense_items",
    )

    item_name = models.CharField(max_length=255)

    # <-- Changed from FloatField to DecimalField for numeric stability -->
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    total_price = models.DecimalField(max_digits=14, decimal_places=2)

    payment_group_id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        supplier_name = self.supplier.name if self.supplier else "No Supplier"
        return f"{self.item_name} - {supplier_name}"

    def clean(self):
        # Use Decimal arithmetic safely
        if self.quantity is None or Decimal(str(self.quantity)) <= Decimal("0"):
            raise ValidationError("Quantity must be greater than zero.")

        if self.unit_price is None or Decimal(self.unit_price) <= Decimal("0.00"):
            raise ValidationError("Unit price must be greater than zero.")

        if not self.payment_group_id:
            raise ValidationError("payment_group_id must not be empty.")

    def save(self, *args, **kwargs):
        # Validate first
        self.clean()

        # Auto-fill item_name from product if product exists and item_name empty
        if self.product and (not self.item_name or self.item_name.strip() == ""):
            try:
                self.item_name = self.product.name
            except Exception:
                logger.debug("Failed to auto-fill item_name from product for ExpenseItem", exc_info=True)

        # Compute and normalize total_price using Decimal arithmetic
        expected_total = (Decimal(str(self.quantity)) * Decimal(self.unit_price)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        self.total_price = expected_total

        super().save(*args, **kwargs)

    @property
    def amount_paid(self) -> Decimal:
        agg = self.payments.aggregate(total=Sum("amount"))
        total = agg.get("total") or Decimal("0.00")
        total_decimal = Decimal(str(total))
        return total_decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def balance(self) -> Decimal:
        bal = Decimal(self.total_price) - self.amount_paid
        if bal < Decimal("0.00"):
            logger.warning(
                "ExpenseItem id=%s has negative balance %.2f — possible data inconsistency.",
                getattr(self, "id", "unsaved"),
                float(bal),
            )
            return Decimal("0.00")
        return bal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def is_fully_paid(self) -> bool:
        return self.balance <= Decimal("0.00")


class ExpensePayment(models.Model):
    expense = models.ForeignKey(ExpenseItem, on_delete=models.CASCADE, related_name="payments")

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-paid_at"]

    def __str__(self):
        return f"Payment {self.amount} for {self.expense}"

    def clean(self):
        amount_dec = Decimal(str(self.amount))
        if amount_dec <= Decimal("0.00"):
            raise ValidationError("Payment amount must be greater than zero.")

        # When validating an update, exclude this payment from the paid_so_far sum
        qs = ExpensePayment.objects.filter(expense=self.expense)
        if self.pk:
            qs = qs.exclude(pk=self.pk)

        agg = qs.aggregate(total=Sum("amount"))
        paid_so_far = agg.get("total") or Decimal("0.00")
        paid_so_far = Decimal(str(paid_so_far))

        new_total = paid_so_far + amount_dec
        if new_total > Decimal(self.expense.total_price):
            raise ValidationError("Payment exceeds total price of the expense item.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
