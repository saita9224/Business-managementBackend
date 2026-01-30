from django.db import models
from employees.models import Employee
import uuid


# ======================================================
# PRICE LISTS (POS SELLING LOGIC)
# ======================================================
class PriceList(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class PriceListItem(models.Model):
    price_list = models.ForeignKey(
        PriceList,
        on_delete=models.CASCADE,
        related_name="items"
    )

    product_id = models.UUIDField()
    product_name = models.CharField(max_length=150)

    selling_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ("price_list", "product_id")

    def __str__(self):
        return f"{self.product_name} @ {self.selling_price}"


# ======================================================
# POS SESSION (CASHIER SHIFT)
# ======================================================
class POSSession(models.Model):
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="pos_sessions"
    )

    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    opening_cash = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    closing_cash = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Session {self.id} - {self.employee.name}"


# ======================================================
# RECEIPT (ANCHOR / GROUPING ENTITY)
# ======================================================
class Receipt(models.Model):
    receipt_number = models.CharField(max_length=50, unique=True)

    session = models.ForeignKey(
        POSSession,
        on_delete=models.PROTECT,
        related_name="receipts"
    )

    created_by = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="created_receipts"
    )

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    status = models.CharField(
        max_length=20,
        choices=[
            ("OPEN", "Open"),
            ("PAID", "Paid"),
            ("CREDIT", "Credit"),
            ("REFUNDED", "Refunded"),
        ],
        default="OPEN"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.receipt_number


# ======================================================
# ORDER (CAN EXIST WITHOUT PAYMENT)
# ======================================================
class Order(models.Model):
    receipt = models.ForeignKey(
        Receipt,
        on_delete=models.CASCADE,
        related_name="orders"
    )

    created_by = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="orders"
    )

    is_saved = models.BooleanField(default=True)
    is_refunded = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order {self.id} ({self.receipt.receipt_number})"


# ======================================================
# ORDER ITEM (PRICE SNAPSHOT & OVERRIDE)
# ======================================================
class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items"
    )

    product_id = models.UUIDField()
    product_name = models.CharField(max_length=150)

    price_list = models.ForeignKey(
        PriceList,
        on_delete=models.PROTECT
    )

    quantity = models.DecimalField(max_digits=10, decimal_places=2)

    # --- PRICE SNAPSHOT ---
    listed_price = models.DecimalField(max_digits=12, decimal_places=2)
    final_price = models.DecimalField(max_digits=12, decimal_places=2)

    price_overridden = models.BooleanField(default=False)
    price_override_by = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="price_overrides"
    )
    price_override_reason = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"


# ======================================================
# PAYMENT (SUPPORTS PARTIAL & MERGED PAYMENTS)
# ======================================================
class Payment(models.Model):
    receipt = models.ForeignKey(
        Receipt,
        on_delete=models.CASCADE,
        related_name="payments"
    )

    method = models.CharField(
        max_length=20,
        choices=[
            ("CASH", "Cash"),
            ("MPESA", "Mpesa"),
            ("CARD", "Card"),
        ]
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    received_by = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="payments_received"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.method} - {self.amount}"


# ======================================================
# CREDIT ACCOUNT (PERMISSION CONTROLLED)
# ======================================================
class CreditAccount(models.Model):
    receipt = models.OneToOneField(
        Receipt,
        on_delete=models.CASCADE,
        related_name="credit_account"
    )

    customer_name = models.CharField(max_length=150)
    customer_phone = models.CharField(max_length=30, blank=True)

    credit_amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField()

    approved_by = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="approved_credits"
    )

    is_settled = models.BooleanField(default=False)

    def __str__(self):
        return f"Credit {self.receipt.receipt_number}"


# ======================================================
# POS → INVENTORY STOCK EMISSION (EVENT ONLY)
# ======================================================
class POSStockMovement(models.Model):
    receipt = models.ForeignKey(
        Receipt,
        on_delete=models.CASCADE,
        related_name="stock_movements"
    )

    product_id = models.UUIDField()
    quantity = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Stock OUT {self.product_id} ({self.quantity})"
