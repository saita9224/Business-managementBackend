# POS/mutations.py

from typing import Optional
from datetime import date

import strawberry
from strawberry.types import Info
from graphql import GraphQLError
from asgiref.sync import sync_to_async

from employees.decorators import permission_required
from inventory.models import Product

from .models import Receipt, Order, POSSession
from .services import (
    open_pos_session,
    close_pos_session,
    create_receipt,
    create_order,
    add_order_item,
    finalize_receipt,
    accept_payment,
    create_credit_account,
    refund_receipt,
)
from .types import (
    POSSessionType,
    ReceiptType,
    OrderType,
    OrderItemType,
    PaymentType,
    CreditAccountType,
)


# ======================================================
# INPUT TYPES
# ======================================================

@strawberry.input
class OpenSessionInput:
    opening_cash: float = 0.0


@strawberry.input
class CloseSessionInput:
    session_id: strawberry.ID
    closing_cash: float


@strawberry.input
class CreateReceiptInput:
    session_id: strawberry.ID
    discount: float = 0.0


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
    due_date: date


@strawberry.input
class RefundReceiptInput:
    receipt_id: strawberry.ID
    reason: str


# ======================================================
# MUTATIONS
# ======================================================

@strawberry.type
class POSMutation:

    # ── SESSION ──────────────────────────────────────────

    @strawberry.mutation
    @permission_required("pos.open_session")
    async def open_pos_session(
        self, info: Info, input: OpenSessionInput
    ) -> POSSessionType:
        user = info.context.user
        try:
            return await sync_to_async(open_pos_session)(
                employee=user,
                opening_cash=input.opening_cash,
            )
        except Exception as e:
            raise GraphQLError(str(e))

    @strawberry.mutation
    @permission_required("pos.close_session")
    async def close_pos_session(
        self, info: Info, input: CloseSessionInput
    ) -> POSSessionType:
        try:
            return await sync_to_async(close_pos_session)(
                session_id=int(input.session_id),
                closing_cash=input.closing_cash,
            )
        except Exception as e:
            raise GraphQLError(str(e))

    # ── RECEIPT ──────────────────────────────────────────

    @strawberry.mutation
    @permission_required("pos.create_order")
    async def create_receipt(
        self, info: Info, input: CreateReceiptInput
    ) -> ReceiptType:
        user = info.context.user
        try:
            session = await sync_to_async(POSSession.objects.get)(
                pk=int(input.session_id),
                is_active=True,
            )
            return await sync_to_async(create_receipt)(
                session=session,
                created_by=user,
                discount=input.discount,
            )
        except POSSession.DoesNotExist:
            raise GraphQLError("Active session not found.")
        except Exception as e:
            raise GraphQLError(str(e))

    # ── ORDER ────────────────────────────────────────────

    @strawberry.mutation
    @permission_required("pos.create_order")
    async def create_order(
        self, info: Info, receipt_id: strawberry.ID
    ) -> OrderType:
        user = info.context.user
        try:
            receipt = await sync_to_async(Receipt.objects.get)(pk=int(receipt_id))
            return await sync_to_async(create_order)(
                receipt=receipt,
                created_by=user,
            )
        except Receipt.DoesNotExist:
            raise GraphQLError("Receipt not found.")
        except Exception as e:
            raise GraphQLError(str(e))

    @strawberry.mutation
    @permission_required("pos.create_order")
    async def add_order_item(
        self, info: Info, input: AddOrderItemInput
    ) -> OrderItemType:
        user = info.context.user
        try:
            order = await sync_to_async(Order.objects.get)(pk=int(input.order_id))
            product = await sync_to_async(Product.objects.get)(pk=int(input.product_id))
            return await sync_to_async(add_order_item)(
                order=order,
                product=product,
                quantity=input.quantity,
                final_price=input.final_price,
                price_override_reason=input.price_override_reason,
                sold_by=user,
            )
        except Order.DoesNotExist:
            raise GraphQLError("Order not found.")
        except Product.DoesNotExist:
            raise GraphQLError("Product not found.")
        except Exception as e:
            raise GraphQLError(str(e))

    # ── FINALIZE ─────────────────────────────────────────

    @strawberry.mutation
    @permission_required("pos.emit_stock")
    async def finalize_receipt(
        self, info: Info, receipt_id: strawberry.ID
    ) -> ReceiptType:
        user = info.context.user
        try:
            receipt = await sync_to_async(Receipt.objects.get)(pk=int(receipt_id))
            return await sync_to_async(finalize_receipt)(
                receipt=receipt,
                performed_by=user,
            )
        except Receipt.DoesNotExist:
            raise GraphQLError("Receipt not found.")
        except Exception as e:
            raise GraphQLError(str(e))

    # ── PAYMENT ──────────────────────────────────────────

    @strawberry.mutation
    @permission_required("pos.accept_payment")
    async def accept_payment(
        self, info: Info, input: AcceptPaymentInput
    ) -> PaymentType:
        user = info.context.user
        try:
            return await sync_to_async(accept_payment)(
                receipt_id=int(input.receipt_id),
                amount=input.amount,
                method=input.method,
                received_by=user,
            )
        except Exception as e:
            raise GraphQLError(str(e))

    # ── CREDIT ───────────────────────────────────────────

    @strawberry.mutation
    @permission_required("pos.create_credit")
    async def create_credit(
        self, info: Info, input: CreateCreditInput
    ) -> CreditAccountType:
        user = info.context.user
        try:
            receipt = await sync_to_async(Receipt.objects.get)(pk=int(input.receipt_id))
            return await sync_to_async(create_credit_account)(
                receipt=receipt,
                customer_name=input.customer_name,
                customer_phone=input.customer_phone,
                due_date=input.due_date,
                approved_by=user,
            )
        except Receipt.DoesNotExist:
            raise GraphQLError("Receipt not found.")
        except Exception as e:
            raise GraphQLError(str(e))

    # ── REFUND ───────────────────────────────────────────

    @strawberry.mutation
    @permission_required("pos.refund_order")
    async def refund_receipt(
        self, info: Info, input: RefundReceiptInput
    ) -> ReceiptType:
        user = info.context.user
        try:
            return await sync_to_async(refund_receipt)(
                receipt_id=int(input.receipt_id),
                reason=input.reason,
                refunded_by=user,
            )
        except Exception as e:
            raise GraphQLError(str(e))