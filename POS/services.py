# pos/services.py

from decimal import Decimal
from uuid import UUID

from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from employees.models import Employee
from employees.permissions import has_permission

from inventory.models import Product
from inventory.services import emit_stock_out  # inventory adapter

from .models import (
    POSSession,
    Receipt,
    Order,
    OrderItem,
    Payment,
    CreditAccount,
    POSStockMovement,
)


#===============================POS SESSION===============================


def open_pos_session(
    *,
    employee: Employee,
    opening_cash: Decimal | float | str = 0
) -> POSSession:

    if not has_permission(employee, "pos.open_session"):
        raise PermissionDenied("You are not allowed to open a POS session.")

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
    employee: Employee,
    session_id: int,
    closing_cash: Decimal | float | str
) -> POSSession:

    session = get_object_or_404(POSSession, id=session_id, is_active=True)

    if not has_permission(employee, "pos.close_session"):
        raise PermissionDenied("You are not allowed to close this POS session.")

    session.closing_cash = Decimal(str(closing_cash))
    session.closed_at = timezone.now()
    session.is_active = False
    session.full_clean()
    session.save()

    return session

#===============================RECEIPT TOTALS===============================


@transaction.atomic
def recalculate_receipt_totals(receipt: Receipt) -> Receipt:
    subtotal = Decimal("0.00")

    for order in receipt.orders.all():
        for item in order.items.all():
            subtotal += item.line_total

    receipt.subtotal = subtotal
    receipt.total = subtotal - receipt.discount
    receipt.full_clean()
    receipt.save()

    return receipt

#===============================PAYMENTS===============================

@transaction.atomic
def accept_payment(
    *,
    employee: Employee,
    receipt_id: int,
    amount: Decimal | float | str,
    method: str,
) -> Payment:

    if not has_permission(employee, "pos.accept_payment"):
        raise PermissionDenied("You are not allowed to accept payments.")

    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValidationError("Payment amount must be greater than zero.")

    receipt = Receipt.objects.select_for_update().get(pk=receipt_id)

    paid_so_far = sum(p.amount for p in receipt.payments.all())
    balance = receipt.total - paid_so_far

    if amount > balance and not has_permission(employee, "pos.partial_payment"):
        raise ValidationError("Overpayment not allowed.")

    payment = Payment(
        receipt=receipt,
        amount=amount,
        method=method,
        received_by=employee,
    )
    payment.full_clean()
    payment.save()

    if amount == balance:
        receipt.status = "PAID"
        receipt.save()

    return payment


#===============================CREDIT SALES===============================

@transaction.atomic
def create_credit_sale(
    *,
    employee: Employee,
    receipt_id: int,
    customer_name: str,
    customer_phone: str | None,
    due_date,
) -> CreditAccount:

    if not has_permission(employee, "pos.create_credit"):
        raise PermissionDenied("Credit sales not allowed.")

    receipt = Receipt.objects.select_for_update().get(pk=receipt_id)

    credit = CreditAccount(
        receipt=receipt,
        customer_name=customer_name,
        customer_phone=customer_phone or "",
        credit_amount=receipt.total,
        due_date=due_date,
        approved_by=employee,
    )
    credit.full_clean()
    credit.save()

    receipt.status = "CREDIT"
    receipt.save()

    return credit



#===============================REFUNDS===============================

@transaction.atomic
def refund_receipt(
    *,
    employee: Employee,
    receipt_id: int,
    reason: str,
) -> Receipt:

    if not has_permission(employee, "pos.refund_order"):
        raise PermissionDenied("Refund permission denied.")

    receipt = Receipt.objects.select_for_update().get(pk=receipt_id)

    if receipt.status not in {"PAID", "CREDIT"}:
        raise ValidationError("Only paid or credit receipts can be refunded.")

    receipt.status = "REFUNDED"
    receipt.save()

    # Stock reversion policy intentionally deferred
    return receipt

#