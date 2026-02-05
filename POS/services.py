# pos/services.py

from decimal import Decimal
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


# =============================== ORDERS ===============================

@transaction.atomic
def create_order(
    *,
    receipt: Receipt,
    created_by: Employee,
) -> Order:

    order = Order(
        receipt=receipt,
        created_by=created_by,
    )
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
    listed_price = product.selling_price

    price_overridden = final_price != listed_price

    if price_overridden and not price_override_reason:
        raise ValidationError("Price override requires a reason.")

    item = OrderItem(
        order=order,
        product=product,
        quantity=quantity,
        listed_price=listed_price,
        final_price=final_price,
        price_overridden=price_overridden,
        price_override_reason=price_override_reason or "",
        sold_by=sold_by,
    )
    item.full_clean()
    item.save()

    return item


# =============================== RECEIPTS ===============================

@transaction.atomic
def finalize_receipt(
    *,
    receipt: Receipt,
    performed_by: Employee,
    emit_stock: bool = True,
) -> Receipt:
    """
    Finalizes receipt:
    - Validates receipt has orders
    - Calculates totals
    - Emits inventory stock ONLY for directly deductible products
    - Always records POS stock audit
    """

    orders = receipt.orders.prefetch_related("items__product")
    if not orders.exists():
        raise ValidationError("A receipt cannot exist without orders.")

    subtotal = Decimal("0.00")

    for order in orders:
        for item in order.items.all():
            line_total = item.final_price * Decimal(item.quantity)
            subtotal += line_total

            # -------------------------------------------------
            # INVENTORY DEDUCTION (STRICTLY PER PRODUCT)
            # -------------------------------------------------
            inventory_deducted = False
            inventory_error = None

            if emit_stock and item.product.auto_deduct_on_sale:
                try:
                    remove_stock(
                        product=item.product,
                        quantity=item.quantity,
                        reason=StockMovement.SALE,
                        performed_by=performed_by,
                        group_id=str(receipt.id),
                    )
                    inventory_deducted = True
                except ValidationError as exc:
                    inventory_error = str(exc)

            # -------------------------------------------------
            # POS AUDIT (ALWAYS RECORDED)
            # -------------------------------------------------
            POSStockMovement.objects.create(
                receipt=receipt,
                product=item.product,
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
