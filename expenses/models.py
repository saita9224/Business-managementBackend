import uuid
from decimal import Decimal, ROUND_HALF_UP
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


# ────────────────────────────────────────────────
# SUPPLIER MODEL
# ────────────────────────────────────────────────
class Supplier(models.Model):
    name = models.CharField(max_length=255, unique=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# ────────────────────────────────────────────────
# EXPENSE ITEM (Main Record)
# ────────────────────────────────────────────────
class ExpenseItem(models.Model):
    supplier = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL, null=True, related_name="expenses"
    )

    # Optional link with Product (lazy reference)
    product = models.ForeignKey(
        "inventory.Product",   # ✔️ FIXED: WAS stock.Product
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expense_items"
    )

    # Always stored — auto-filled if product is selected
    item_name = models.CharField(max_length=255)

    quantity = models.FloatField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    # System-calculated field (kept for easier queries)
    total_price = models.DecimalField(max_digits=14, decimal_places=2)

    # Group payments (unique)
    payment_group_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        supplier_name = self.supplier.name if self.supplier else "No Supplier"
        return f"{self.item_name} - {supplier_name}"

    # ────────────────────────────────────────────────
    # Auto-fill + Validation
    # ────────────────────────────────────────────────
    def clean(self):
        # Validate quantity & price
        if self.quantity is None or self.quantity <= 0:
            raise ValidationError("Quantity must be greater than zero.")

        if self.unit_price is None or Decimal(self.unit_price) <= Decimal("0.00"):
            raise ValidationError("Unit price must be greater than zero.")

        # Auto-fill item_name from product if product exists
        if self.product:
            # if frontend supplied a custom name, we allow override; but default to product.name
            if not self.item_name:
                self.item_name = self.product.name

        # Compute and normalize total_price
        expected_total = (Decimal(str(self.quantity)) * Decimal(self.unit_price)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        # set total_price to expected (avoid raising here — keep consistent)
        self.total_price = expected_total

        # payment_group_id is auto-populated by default; no need to raise unless empty
        if not self.payment_group_id:
            raise ValidationError("payment_group_id must not be empty.")

    def save(self, *args, **kwargs):
        # Ensure model is clean and totals are correct before saving
        self.clean()
        super().save(*args, **kwargs)

    @property
    def amount_paid(self) -> Decimal:
        """Total amount paid for this item (sum of payments)."""
        total = Decimal("0.00")
        for p in self.payments.all():
            total += Decimal(p.amount)
        return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def balance(self) -> Decimal:
        """Remaining unpaid balance."""
        bal = Decimal(self.total_price) - self.amount_paid
        # Clamp negative balances to 0.00
        if bal < Decimal("0.00"):
            return Decimal("0.00")
        return bal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def is_fully_paid(self) -> bool:
        return self.balance <= Decimal("0.00")


# ────────────────────────────────────────────────
# EXPENSE PAYMENT (Tracks Installments)
# ────────────────────────────────────────────────
class ExpensePayment(models.Model):
    # FK named `expense` to match service usage
    expense = models.ForeignKey(
        ExpenseItem,
        on_delete=models.CASCADE,
        related_name="payments"
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-paid_at"]

    def __str__(self):
        return f"Payment {self.amount} for {self.expense}"

    # ────────────────────────────────────────────────
    # Validate payment limits
    # ────────────────────────────────────────────────
    def clean(self):
        if Decimal(str(self.amount)) <= Decimal("0.00"):
            raise ValidationError("Payment amount must be greater than zero.")

        # Use expense.amount_paid which sums existing payments (not including this one)
        paid_so_far = self.expense.amount_paid
        new_total = paid_so_far + Decimal(str(self.amount))

        if new_total > Decimal(self.expense.total_price):
            raise ValidationError("Payment exceeds total price of the expense item.")

    def save(self, *args, **kwargs):
        # Always run validation before saving
        self.clean()
        super().save(*args, **kwargs)
