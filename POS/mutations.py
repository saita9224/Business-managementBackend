# POS/mutations.py

from typing import Optional
from datetime import date

import strawberry
from strawberry.types import Info

from employees.decorators import permission_required

from inventory.models import Product

from .models import Receipt, Order
from .services import (
    open_pos_session,
    close_pos_session,
    create_order,
    add_order_item,
    finalize_receipt,
    accept_payment,
    create_credit_account,
    refund_receipt,
)
from .types import (
    POSSessionType,
    OrderType,
    OrderItemType,
    ReceiptType,
    PaymentType,
    CreditAccountType,
)


# ============================================================
# INPUT TYPES
# ============================================================

@strawberry.input
class OpenSessionInput:
    opening_cash: float = 0.0


@strawberry.input
class CloseSessionInput:
    session_id: strawberry.ID
    closing_cash: float


@strawberry.input
class AddOrderItemInput:
    order_id: strawberry.ID
    product_id: strawberry.ID
    quantity: float
    final_price: float
    price_override_reason: Optional[str] = None


@strawberry.input
class AcceptPaymentInput:
    receipt_id: strawberry.ID
    amount: float
    method: str


@strawberry.input
class CreateCreditInput:
    receipt_id: strawberry.ID
    customer_name: str
    customer_phone: Optional[str] = None
    due_date: date   # ✅ FIXED (was strawberry.Date ❌)


@strawberry.input
class RefundReceiptInput:
    receipt_id: strawberry.ID
    reason: str


# ============================================================
# MUTATIONS
# ============================================================

@strawberry.type
class POSMutation:

    # ====================== SESSION ======================

    @strawberry.mutation
    @permission_required("pos.open_session")
    async def open_pos_session(
        self,
        info: Info,
        input: OpenSessionInput,
    ) -> POSSessionType:

        user = info.context.user

        return open_pos_session(
            employee=user,
            opening_cash=input.opening_cash,
        )


    @strawberry.mutation
    @permission_required("pos.close_session")
    async def close_pos_session(
        self,
        info: Info,
        input: CloseSessionInput,
    ) -> POSSessionType:

        return close_pos_session(
            session_id=int(input.session_id),
            closing_cash=input.closing_cash,
        )


    # ====================== ORDER ======================

    @strawberry.mutation
    @permission_required("pos.create_order")
    async def create_order(
        self,
        info: Info,
        receipt_id: strawberry.ID,
    ) -> OrderType:

        user = info.context.user
        receipt = Receipt.objects.get(pk=int(receipt_id))

        return create_order(
            receipt=receipt,
            created_by=user,
        )


    @strawberry.mutation
    @permission_required("pos.create_order")
    async def add_order_item(
        self,
        info: Info,
        input: AddOrderItemInput,
    ) -> OrderItemType:

        user = info.context.user

        order = Order.objects.get(pk=int(input.order_id))
        product = Product.objects.get(pk=int(input.product_id))

        return add_order_item(
            order=order,
            product=product,
            quantity=input.quantity,
            final_price=input.final_price,
            price_override_reason=input.price_override_reason,
            sold_by=user,
        )


    # ====================== RECEIPT ======================

    @strawberry.mutation
    @permission_required("pos.emit_stock")
    async def finalize_receipt(
        self,
        info: Info,
        receipt_id: strawberry.ID,
    ) -> ReceiptType:

        user = info.context.user
        receipt = Receipt.objects.get(pk=int(receipt_id))

        return finalize_receipt(
            receipt=receipt,
            performed_by=user,
        )


    # ====================== PAYMENTS ======================

    @strawberry.mutation
    @permission_required("pos.accept_payment")
    async def accept_payment(
        self,
        info: Info,
        input: AcceptPaymentInput,
    ) -> PaymentType:

        user = info.context.user

        return accept_payment(
            receipt_id=int(input.receipt_id),
            amount=input.amount,
            method=input.method,
            received_by=user,
        )


    # ====================== CREDIT ======================

    @strawberry.mutation
    @permission_required("pos.create_credit")
    async def create_credit(
        self,
        info: Info,
        input: CreateCreditInput,
    ) -> CreditAccountType:

        user = info.context.user
        receipt = Receipt.objects.get(pk=int(input.receipt_id))

        return create_credit_account(
            receipt=receipt,
            customer_name=input.customer_name,
            customer_phone=input.customer_phone,
            due_date=input.due_date,
            approved_by=user,
        )


    # ====================== REFUND ======================

    @strawberry.mutation
    @permission_required("pos.refund_order")
    async def refund_receipt(
        self,
        info: Info,
        input: RefundReceiptInput,
    ) -> ReceiptType:

        user = info.context.user

        return refund_receipt(
            receipt_id=int(input.receipt_id),
            reason=input.reason,
            refunded_by=user,
        )
