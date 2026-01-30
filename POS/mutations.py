# pos/mutation.py

from typing import Optional, List
from decimal import Decimal
from datetime import date
from uuid import UUID

import strawberry
from strawberry.types import Info
from django.core.exceptions import ValidationError, PermissionDenied

from employees.models import Employee
from employees.permissions import has_permission

from . import services
from .models import Receipt, Order, OrderItem
from .types import (
    POSSessionType,
    ReceiptType,
    OrderType,
    PaymentType,
    CreditAccountType,
)


# ======================================================
# INPUT TYPES
# ======================================================

@strawberry.input
class OrderItemInput:
    product_id: strawberry.ID
    product_name: str
    quantity: Decimal
    unit_price: Decimal

    overridden_price: Optional[Decimal] = None
    override_reason: Optional[str] = None


# ======================================================
# POS MUTATIONS
# ======================================================

@strawberry.type
class POSMutation:

    # -------------------------------
    # POS SESSION
    # -------------------------------

    @strawberry.mutation
    def open_pos_session(
        self,
        info: Info,
        opening_cash: Decimal = Decimal("0.00"),
    ) -> POSSessionType:
        employee: Employee = info.context["employee"]

        return services.open_pos_session(
            employee=employee,
            opening_cash=opening_cash,
        )

    @strawberry.mutation
    def close_pos_session(
        self,
        info: Info,
        session_id: strawberry.ID,
        closing_cash: Decimal,
    ) -> POSSessionType:
        employee: Employee = info.context["employee"]

        return services.close_pos_session(
            employee=employee,
            session_id=int(session_id),
            closing_cash=closing_cash,
        )

    # -------------------------------
    # RECEIPT & ORDER CREATION
    # -------------------------------

    @strawberry.mutation
    def create_receipt(
        self,
        info: Info,
        session_id: strawberry.ID,
        receipt_number: str,
    ) -> ReceiptType:
        """
        Creates an EMPTY receipt.
        Receipt is not valid for payment until orders exist.
        """
        employee: Employee = info.context["employee"]

        receipt = Receipt(
            receipt_number=receipt_number,
            session_id=int(session_id),
            created_by=employee,
            subtotal=Decimal("0.00"),
            discount=Decimal("0.00"),
            total=Decimal("0.00"),
            status="OPEN",
        )
        receipt.full_clean()
        receipt.save()

        return receipt

    @strawberry.mutation
    def save_order(
        self,
        info: Info,
        receipt_id: strawberry.ID,
        items: List[OrderItemInput],
    ) -> OrderType:
        """
        Saves an order and emits stock events.
        POS NEVER blocks sales due to inventory state.
        """
        employee: Employee = info.context["employee"]

        if not items:
            raise ValidationError("An order must contain at least one item.")

        receipt = Receipt.objects.get(pk=int(receipt_id))

        order = Order(
            receipt=receipt,
            created_by=employee,
            is_saved=True,
        )
        order.full_clean()
        order.save()

        for item in items:
            # ---------------------------
            # PRICE OVERRIDE VALIDATION
            # ---------------------------
            if item.overridden_price is not None:
                if not has_permission(employee, "pos.override_price"):
                    raise PermissionDenied("Price override not permitted.")

                if not item.override_reason:
                    raise ValidationError("Price override reason is required.")

                overridden_price = Decimal(item.overridden_price)
                effective_price = overridden_price
            else:
                overridden_price = None
                effective_price = Decimal(item.unit_price)

            quantity = Decimal(item.quantity)
            line_total = quantity * effective_price

            order_item = OrderItem(
                order=order,
                product_id=UUID(str(item.product_id)),
                product_name=item.product_name,
                quantity=quantity,
                unit_price=Decimal(item.unit_price),
                overridden_price=overridden_price,
                price_override_by=employee if overridden_price else None,
                line_total=line_total,
            )
            order_item.full_clean()
            order_item.save()

            # ---------------------------
            # STOCK EMISSION (NON-BLOCKING)
            # ---------------------------
            try:
                services.emit_stock_out(
                    receipt=receipt,
                    product_id=order_item.product_id,
                    quantity=order_item.quantity,
                )
            except Exception:
                # Inventory is advisory — never block POS
                pass

        services.recalculate_receipt_totals(receipt)

        return order

    # -------------------------------
    # PAYMENTS
    # -------------------------------

    @strawberry.mutation
    def accept_payment(
        self,
        info: Info,
        receipt_id: strawberry.ID,
        amount: Decimal,
        method: str,
    ) -> PaymentType:
        employee: Employee = info.context["employee"]

        receipt = Receipt.objects.get(pk=int(receipt_id))
        if not receipt.orders.exists():
            raise ValidationError("Cannot pay for a receipt with no orders.")

        return services.accept_payment(
            employee=employee,
            receipt_id=int(receipt_id),
            amount=amount,
            method=method,
        )

    # -------------------------------
    # CREDIT SALES
    # -------------------------------

    @strawberry.mutation
    def create_credit_sale(
        self,
        info: Info,
        receipt_id: strawberry.ID,
        customer_name: str,
        customer_phone: Optional[str],
        due_date: date,
    ) -> CreditAccountType:
        employee: Employee = info.context["employee"]

        receipt = Receipt.objects.get(pk=int(receipt_id))
        if not receipt.orders.exists():
            raise ValidationError("Cannot credit a receipt with no orders.")

        return services.create_credit_sale(
            employee=employee,
            receipt_id=int(receipt_id),
            customer_name=customer_name,
            customer_phone=customer_phone,
            due_date=due_date,
        )

    # -------------------------------
    # REFUNDS
    # -------------------------------

    @strawberry.mutation
    def refund_receipt(
        self,
        info: Info,
        receipt_id: strawberry.ID,
        reason: str,
    ) -> ReceiptType:
        employee: Employee = info.context["employee"]

        if not reason:
            raise ValidationError("Refund reason is required.")

        return services.refund_receipt(
            employee=employee,
            receipt_id=int(receipt_id),
            reason=reason,
        )
