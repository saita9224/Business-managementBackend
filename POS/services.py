# POS/services.py

from decimal import Decimal
from datetime import datetime
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from employees.models import Employee
from inventory.models import Product, StockMovement
from inventory.services import remove_stock

from .models import (
    POSSession,
    Receipt,
    Order,
    OrderItem,
    Payment,
    CreditAccount,
    POSStockMovement,
)


# =============================== POS SESSION ===============================

def open_pos_session(
    *,
    employee: Employee,
    opening_cash: Decimal | float | str = 0,
) -> POSSession:

    if POSSession.objects.filter(employee=employee, is_active=True).exists():
        raise ValidationError("Employee already has an active POS session.")

    session = POSSession(
        employee=employee,
        opening_cash=Decimal(str(opening_cash)),
    )
    session.full_clean()
    session.save()
    return session


def close_pos_session(
    *,
    session_id: int,
    closing_cash: Decimal | float | str,
) -> POSSession:

    session = get_object_or_404(POSSession, id=session_id, is_active=True)
    session.closing_cash = Decimal(str(closing_cash))
    session.closed_at = timezone.now()
    session.is_active = False
    session.full_clean()
    session.save()
    return session


# =============================== RECEIPT CREATION ===============================

@transaction.atomic
def create_receipt(
    *,
    session: POSSession,
    created_by: Employee,
    discount: Decimal | float | str = 0,
) -> Receipt:
    """
    Creates a new empty receipt under the given session.
    Receipt number is generated after save to include the DB-assigned ID.
    Format: RCP-YYYYMMDD-{id zero-padded to 4 digits}
    """
    receipt = Receipt(
        receipt_number="PENDING",
        session=session,
        created_by=created_by,
        discount=Decimal(str(discount)),
    )
    receipt.save()

    receipt.receipt_number = (
        f"RCP-{datetime.now().strftime('%Y%m%d')}-{str(receipt.id).zfill(4)}"
    )
    receipt.save(update_fields=["receipt_number"])
    return receipt


# =============================== ORDERS ===============================

@transaction.atomic
def create_order(
    *,
    receipt: Receipt,
    created_by: Employee,
) -> Order:

    order = Order(receipt=receipt, created_by=created_by)
    order.full_clean()
    order.save()
    return order


@transaction.atomic
def add_order_item(
    *,
    order: Order,
    product: Product,
    quantity: float,
    final_price: Decimal | float | str,
    sold_by: Employee,
    price_override_reason: str | None = None,
) -> OrderItem:

    if quantity <= 0:
        raise ValidationError("Quantity must be greater than zero.")

    final_price = Decimal(str(final_price))

    from .models import PriceListItem, PriceList
    try:
        default_price_list = PriceList.objects.get(is_default=True)
        price_list_item = PriceListItem.objects.get(
            price_list=default_price_list,
            product_id=product.id,
        )
        listed_price = price_list_item.selling_price
        price_list = default_price_list
    except (PriceList.DoesNotExist, PriceListItem.DoesNotExist):
        listed_price = final_price
        price_list = PriceList.objects.filter(is_default=True).first()
        if not price_list:
            raise ValidationError(
                "No default price list found. Please configure one before selling."
            )

    price_overridden = final_price != listed_price

    if price_overridden and not price_override_reason:
        raise ValidationError("Price override requires a reason.")

    line_total = final_price * Decimal(str(quantity))

    item = OrderItem(
        order=order,
        product_id=product.id,
        product_name=product.name,
        price_list=price_list,
        quantity=Decimal(str(quantity)),
        listed_price=listed_price,
        final_price=final_price,
        price_overridden=price_overridden,
        price_override_reason=price_override_reason or "",
        sold_by=sold_by,
        line_total=line_total,
    )
    item.full_clean()
    item.save()
    return item


# =============================== FINALIZE ===============================

@transaction.atomic
def finalize_receipt(
    *,
    receipt: Receipt,
    performed_by: Employee,
    emit_stock: bool = True,
) -> Receipt:
    """
    Finalizes a receipt:
    - Calculates subtotal and total from all order items.
    - Per item: attempts stock deduction inside a savepoint.
      - If deduction succeeds → audit: deducted_from_inventory=True
      - If deduction fails   → savepoint rolls back StockMovement only.
                               Audit record still written with deducted_from_inventory=False
                               and the error captured in notes.
                               Receipt finalization is NOT blocked.
    """

    orders = receipt.orders.prefetch_related("items")
    if not orders.exists():
        raise ValidationError("Receipt has no orders.")

    subtotal = Decimal("0.00")

    for order in orders:
        for item in order.items.all():
            subtotal += item.final_price * item.quantity

            inventory_deducted = False
            inventory_error = None
            product = None

            # ── Fetch product for stock deduction + audit ──────────
            try:
                product = Product.objects.get(pk=item.product_id)
            except Product.DoesNotExist:
                inventory_error = f"Product {item.product_id} not found in inventory"

            # ── Attempt stock deduction inside a savepoint ──────────
            # Nested transaction.atomic() = savepoint inside outer @transaction.atomic
            # If it raises, only the savepoint rolls back — receipt is unaffected
            if emit_stock and product is not None and product.auto_deduct_on_sale:
                try:
                    with transaction.atomic():
                        remove_stock(
                            product=product,
                            quantity=float(item.quantity),
                            reason=StockMovement.SALE,
                            performed_by=performed_by,
                            group_id=str(receipt.id),
                        )
                        inventory_deducted = True
                except ValidationError as exc:
                    inventory_error = str(exc)
                except Exception as exc:
                    inventory_error = f"Unexpected error: {str(exc)}"

            # ── Audit record — always written ───────────────────────
            if product is not None:
                POSStockMovement.objects.create(
                    receipt=receipt,
                    product=product,
                    quantity=item.quantity,
                    deducted_from_inventory=inventory_deducted,
                    notes=inventory_error or "",
                    performed_by=performed_by,
                )

    receipt.subtotal = subtotal
    receipt.total = subtotal - receipt.discount
    receipt.status = Receipt.OPEN
    receipt.full_clean()
    receipt.save()
    return receipt


# =============================== PAYMENTS ===============================

@transaction.atomic
def accept_payment(
    *,
    receipt_id: int,
    amount: Decimal | float | str,
    method: str,
    received_by: Employee,
) -> Payment:

    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValidationError("Payment amount must be greater than zero.")

    receipt = Receipt.objects.select_for_update().get(pk=receipt_id)
    paid = sum(p.amount for p in receipt.payments.all())
    balance = receipt.total - paid

    if amount > balance:
        raise ValidationError("Payment exceeds remaining balance.")

    payment = Payment(
        receipt=receipt,
        amount=amount,
        method=method,
        received_by=received_by,
    )
    payment.full_clean()
    payment.save()

    if amount == balance:
        receipt.status = Receipt.PAID
        receipt.save(update_fields=["status"])

    return payment


# =============================== CREDIT ===============================

@transaction.atomic
def create_credit_account(
    *,
    receipt: Receipt,
    customer_name: str,
    customer_phone: str | None,
    due_date,
    approved_by: Employee,
) -> CreditAccount:

    credit = CreditAccount(
        receipt=receipt,
        customer_name=customer_name,
        customer_phone=customer_phone or "",
        credit_amount=receipt.total,
        due_date=due_date,
        approved_by=approved_by,
    )
    credit.full_clean()
    credit.save()

    receipt.status = Receipt.CREDIT
    receipt.save(update_fields=["status"])
    return credit


# =============================== REFUNDS ===============================

@transaction.atomic
def refund_receipt(
    *,
    receipt_id: int,
    reason: str,
    refunded_by: Employee,
) -> Receipt:

    receipt = Receipt.objects.select_for_update().get(pk=receipt_id)

    if receipt.status not in {Receipt.PAID, Receipt.CREDIT}:
        raise ValidationError("Only paid or credit receipts can be refunded.")

    receipt.status = Receipt.REFUNDED
    receipt.refund_reason = reason
    receipt.refunded_by = refunded_by
    receipt.refunded_at = timezone.now()
    receipt.save()
    return receipt