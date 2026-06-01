from typing import Optional
from datetime import date

import strawberry
from strawberry.types import Info
from graphql import GraphQLError
from asgiref.sync import sync_to_async

from employees.decorators import permission_required
from inventory.models import Product

from .models import Receipt, Order, POSSession, CreditAccount, MenuItem
from .services import (
    open_pos_session,
    close_pos_session,
    create_receipt          as svc_create_receipt,
    delete_draft_receipt    as svc_delete_draft_receipt,
    create_order            as svc_create_order,
    add_order_item          as svc_add_order_item,
    add_menu_order_item     as svc_add_menu_order_item,
    submit_order            as svc_submit_order,
    recall_order            as svc_recall_order,
    accept_payment          as svc_accept_payment,
    create_credit_account   as svc_create_credit,
    settle_credit           as svc_settle_credit,
    refund_receipt          as svc_refund_receipt,
    create_menu_item        as svc_create_menu_item,
    update_menu_item        as svc_update_menu_item,
    delete_menu_item        as svc_delete_menu_item,
)
from .types import (
    POSSessionType,
    ReceiptType,
    OrderType,
    OrderItemType,
    PaymentType,
    CreditAccountType,
    MenuItemType,
)


def _fetch_receipt(pk: int) -> Receipt:
    return (
        Receipt.objects
        .select_related(
            "session",
            "session__employee",
            "created_by",
            "refunded_by",
        )
        .get(pk=pk)
    )


# ======================================================
# INPUT TYPES
# ======================================================

@strawberry.input
class OpenSessionInput:
    opening_cash: float = 0.0


@strawberry.input
class CloseSessionInput:
    session_id:   strawberry.ID
    closing_cash: float


@strawberry.input
class CreateReceiptInput:
    session_id: strawberry.ID
    discount:   float = 0.0
    table_note: str   = ""


@strawberry.input
class AddOrderItemInput:
    order_id:              strawberry.ID
    product_id:            strawberry.ID
    quantity:              float
    final_price:           float
    price_override_reason: Optional[str] = None


@strawberry.input
class AddMenuOrderItemInput:
    order_id:     strawberry.ID
    menu_item_id: strawberry.ID
    quantity:     float


@strawberry.input
class AcceptPaymentInput:
    receipt_id: strawberry.ID
    amount:     float
    method:     str


@strawberry.input
class CreateCreditInput:
    receipt_id:     strawberry.ID
    customer_name:  str
    customer_phone: Optional[str] = None
    due_date:       date


@strawberry.input
class SettleCreditInput:
    credit_id: strawberry.ID
    amount:    float
    method:    str


@strawberry.input
class RefundReceiptInput:
    receipt_id: strawberry.ID
    reason:     str


@strawberry.input
class CreateMenuItemInput:
    name:       str
    emoji:      str
    price:      float
    category:   str  = "other"
    is_pinned:  bool = False
    product_id: Optional[strawberry.ID] = None


@strawberry.input
class UpdateMenuItemInput:
    item_id:      strawberry.ID
    name:         Optional[str]   = None
    emoji:        Optional[str]   = None
    price:        Optional[float] = None
    category:     Optional[str]   = None
    is_pinned:    Optional[bool]  = None
    is_available: Optional[bool]  = None


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
            session = await sync_to_async(
                POSSession.objects.select_related("employee").get
            )(pk=int(input.session_id), is_active=True)
            receipt = await sync_to_async(svc_create_receipt)(
                session=session,
                created_by=user,
                discount=input.discount,
                table_note=input.table_note,
            )
            return await sync_to_async(_fetch_receipt)(receipt.id)
        except POSSession.DoesNotExist:
            raise GraphQLError("Active session not found.")
        except Exception as e:
            raise GraphQLError(str(e))

    # ── ORDER ────────────────────────────────────────────

    @strawberry.mutation
    @permission_required("pos.create_order")
    async def delete_draft_receipt(
        self, info: Info, receipt_id: strawberry.ID
    ) -> bool:
        user = info.context.user
        try:
            return await sync_to_async(svc_delete_draft_receipt)(
                receipt_id=int(receipt_id),
                deleted_by=user,
            )
        except Receipt.DoesNotExist:
            raise GraphQLError("Receipt not found.")
        except Exception as e:
            raise GraphQLError(str(e))

    @strawberry.mutation
    @permission_required("pos.create_order")
    async def create_order(
        self, info: Info, receipt_id: strawberry.ID
    ) -> OrderType:
        user = info.context.user
        try:
            receipt = await sync_to_async(_fetch_receipt)(int(receipt_id))
            return await sync_to_async(svc_create_order)(
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
            order   = await sync_to_async(
                Order.objects.select_related("receipt", "created_by").get
            )(pk=int(input.order_id))
            product = await sync_to_async(Product.objects.get)(pk=int(input.product_id))

            menu_item = await sync_to_async(
                lambda: getattr(product, "menu_item", None)
            )()

            return await sync_to_async(svc_add_order_item)(
                order=order,
                product=product,
                quantity=input.quantity,
                final_price=input.final_price,
                price_override_reason=input.price_override_reason,
                sold_by=user,
                menu_item=menu_item,
            )
        except Order.DoesNotExist:
            raise GraphQLError("Order not found.")
        except Product.DoesNotExist:
            raise GraphQLError("Product not found.")
        except Exception as e:
            raise GraphQLError(str(e))

    @strawberry.mutation
    @permission_required("pos.create_order")
    async def add_menu_order_item(
        self, info: Info, input: AddMenuOrderItemInput
    ) -> OrderItemType:
        user = info.context.user
        try:
            order     = await sync_to_async(
                Order.objects.select_related("receipt", "created_by").get
            )(pk=int(input.order_id))
            menu_item = await sync_to_async(MenuItem.objects.get)(pk=int(input.menu_item_id))
            return await sync_to_async(svc_add_menu_order_item)(
                order=order,
                menu_item=menu_item,
                quantity=input.quantity,
                sold_by=user,
            )
        except Order.DoesNotExist:
            raise GraphQLError("Order not found.")
        except MenuItem.DoesNotExist:
            raise GraphQLError("Menu item not found.")
        except Exception as e:
            raise GraphQLError(str(e))

    # ── SUBMIT ───────────────────────────────────────────

    @strawberry.mutation
    @permission_required("pos.create_order")
    async def submit_order(
        self, info: Info, receipt_id: strawberry.ID
    ) -> ReceiptType:
        user = info.context.user
        try:
            receipt = await sync_to_async(_fetch_receipt)(int(receipt_id))
            result  = await sync_to_async(svc_submit_order)(
                receipt=receipt,
                performed_by=user,
            )
            return await sync_to_async(_fetch_receipt)(result.id)
        except Receipt.DoesNotExist:
            raise GraphQLError("Receipt not found.")
        except Exception as e:
            raise GraphQLError(str(e))

    # ── RECALL ───────────────────────────────────────────

    @strawberry.mutation
    @permission_required("pos.recall_order")
    async def recall_order(
        self, info: Info, receipt_id: strawberry.ID
    ) -> ReceiptType:
        user = info.context.user
        try:
            receipt    = await sync_to_async(_fetch_receipt)(int(receipt_id))
            creator_id = await sync_to_async(lambda: receipt.created_by_id)()
            if creator_id != user.id:
                raise GraphQLError("You can only recall your own orders.")
            result = await sync_to_async(svc_recall_order)(
                receipt=receipt,
                recalled_by=user,
            )
            return await sync_to_async(_fetch_receipt)(result.id)
        except Receipt.DoesNotExist:
            raise GraphQLError("Receipt not found.")
        except GraphQLError:
            raise
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
            return await sync_to_async(svc_accept_payment)(
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
            receipt = await sync_to_async(_fetch_receipt)(int(input.receipt_id))
            return await sync_to_async(svc_create_credit)(
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

    # ── SETTLE CREDIT ─────────────────────────────────────

    @strawberry.mutation
    @permission_required("pos.settle_credit")
    async def settle_credit(
        self, info: Info, input: SettleCreditInput
    ) -> PaymentType:
        user = info.context.user
        try:
            return await sync_to_async(svc_settle_credit)(
                credit_id=int(input.credit_id),
                amount=input.amount,
                method=input.method,
                settled_by=user,
            )
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
            result = await sync_to_async(svc_refund_receipt)(
                receipt_id=int(input.receipt_id),
                reason=input.reason,
                refunded_by=user,
            )
            return await sync_to_async(_fetch_receipt)(result.id)
        except Exception as e:
            raise GraphQLError(str(e))

    # ── MENU ─────────────────────────────────────────────

    @strawberry.mutation
    @permission_required("pos.manage_menu")
    async def create_menu_item(
        self, info: Info, input: CreateMenuItemInput
    ) -> MenuItemType:
        try:
            return await sync_to_async(svc_create_menu_item)(
                name=input.name,
                emoji=input.emoji,
                price=input.price,
                category=input.category,
                is_pinned=input.is_pinned,
                product_id=int(input.product_id) if input.product_id else None,
            )
        except Exception as e:
            raise GraphQLError(str(e))

    @strawberry.mutation
    @permission_required("pos.manage_menu")
    async def update_menu_item(
        self, info: Info, input: UpdateMenuItemInput
    ) -> MenuItemType:
        try:
            return await sync_to_async(svc_update_menu_item)(
                item_id=int(input.item_id),
                name=input.name,
                emoji=input.emoji,
                price=float(input.price) if input.price is not None else None,
                category=input.category,
                is_pinned=input.is_pinned,
                is_available=input.is_available,
            )
        except Exception as e:
            raise GraphQLError(str(e))

    @strawberry.mutation
    @permission_required("pos.manage_menu")
    async def delete_menu_item(
        self, info: Info, item_id: strawberry.ID
    ) -> bool:
        try:
            return await sync_to_async(svc_delete_menu_item)(item_id=int(item_id))
        except Exception as e:
            raise GraphQLError(str(e))