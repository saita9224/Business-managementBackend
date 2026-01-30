# pos/types.py

from typing import List, Optional
from datetime import datetime, date
from decimal import Decimal

import strawberry
from strawberry.types import Info

from employees.types import UserType
from .models import (
    POSSession,
    Receipt,
    Order,
    OrderItem,
    Payment,
    CreditAccount,
    POSStockMovement,
)

# ======================================================
# POS SESSION
# ======================================================

@strawberry.type
class POSSessionType:
    id: strawberry.ID
    opened_at: datetime
    closed_at: Optional[datetime]
    opening_cash: Decimal
    closing_cash: Optional[Decimal]
    is_active: bool

    employee: UserType

    @strawberry.field
    async def receipts(self, info: Info) -> List["ReceiptType"]:
        return await info.context["receipts_by_session"].load(self.id)


# ======================================================
# RECEIPT (ANCHOR ENTITY)
# ======================================================

@strawberry.type
class ReceiptType:
    id: strawberry.ID
    receipt_number: str
    subtotal: Decimal
    discount: Decimal
    total: Decimal
    status: str
    created_at: datetime

    session: POSSessionType
    created_by: UserType

    @strawberry.field
    async def orders(self, info: Info) -> List["OrderType"]:
        return await info.context["orders_by_receipt"].load(self.id)

    @strawberry.field
    async def payments(self, info: Info) -> List["PaymentType"]:
        return await info.context["payments_by_receipt"].load(self.id)

    @strawberry.field
    async def credit(self, info: Info) -> Optional["CreditAccountType"]:
        return await info.context["credit_by_receipt"].load(self.id)

    @strawberry.field
    async def stock_movements(self, info: Info) -> List["POSStockMovementType"]:
        return await info.context["stock_by_receipt"].load(self.id)

    @strawberry.field
    async def balance(self, info: Info) -> Decimal:
        payments = await info.context["payments_by_receipt"].load(self.id)
        paid = sum(p.amount for p in payments)
        return self.total - paid


# ======================================================
# ORDER
# ======================================================

@strawberry.type
class OrderType:
    id: strawberry.ID
    is_saved: bool
    is_refunded: bool
    created_at: datetime

    created_by: UserType

    @strawberry.field
    async def items(self, info: Info) -> List["OrderItemType"]:
        return await info.context["items_by_order"].load(self.id)


# ======================================================
# ORDER ITEM (PRICE OVERRIDE LIVES HERE)
# ======================================================

@strawberry.type
class OrderItemType:
    id: strawberry.ID
    product_id: strawberry.ID
    product_name: str

    quantity: Decimal
    unit_price: Decimal
    overridden_price: Optional[Decimal]
    line_total: Decimal

    price_override_by: Optional[UserType]

    @strawberry.field
    def effective_price(self) -> Decimal:
        return self.overridden_price or self.unit_price


# ======================================================
# PAYMENT
# ======================================================

@strawberry.type
class PaymentType:
    id: strawberry.ID
    method: str
    amount: Decimal
    created_at: datetime

    received_by: UserType


# ======================================================
# CREDIT ACCOUNT
# ======================================================

@strawberry.type
class CreditAccountType:
    id: strawberry.ID
    customer_name: str
    customer_phone: Optional[str]
    credit_amount: Decimal
    due_date: date
    is_settled: bool

    approved_by: UserType


# ======================================================
# POS → INVENTORY STOCK EVENT (READ-ONLY / AUDIT)
# ======================================================

@strawberry.type
class POSStockMovementType:
    id: strawberry.ID
    product_id: strawberry.ID
    quantity: Decimal
    created_at: datetime
