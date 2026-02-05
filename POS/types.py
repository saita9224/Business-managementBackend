# pos/types.py

from typing import List, Optional, TYPE_CHECKING
from datetime import datetime, date
from decimal import Decimal

import strawberry
from strawberry.types import Info

from employees.types import EmployeeType 

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

    employee: "EmployeeType"

    @strawberry.field
    async def receipts(self, info: Info) -> List["ReceiptType"]:
        return await info.context["receipts_by_session"].load(int(self.id))


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
    created_by: "EmployeeType"

    @strawberry.field
    async def orders(self, info: Info) -> List["OrderType"]:
        return await info.context["orders_by_receipt"].load(int(self.id))

    @strawberry.field
    async def payments(self, info: Info) -> List["PaymentType"]:
        return await info.context["payments_by_receipt"].load(int(self.id))

    @strawberry.field
    async def credit(self, info: Info) -> Optional["CreditAccountType"]:
        return await info.context["credit_by_receipt"].load(int(self.id))

    @strawberry.field
    async def stock_movements(self, info: Info) -> List["POSStockMovementType"]:
        return await info.context["stock_by_receipt"].load(int(self.id))

    @strawberry.field
    async def balance(self, info: Info) -> Decimal:
        payments = await info.context["payments_by_receipt"].load(int(self.id))
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

    created_by: "EmployeeType"

    @strawberry.field
    async def items(self, info: Info) -> List["OrderItemType"]:
        return await info.context["items_by_order"].load(int(self.id))


# ======================================================
# ORDER ITEM (PRICE SNAPSHOT + OVERRIDE)
# ======================================================

@strawberry.type
class OrderItemType:
    id: strawberry.ID
    product_id: strawberry.ID
    product_name: str

    quantity: Decimal

    listed_price: Decimal
    final_price: Decimal

    price_overridden: bool
    price_override_reason: Optional[str]
    price_override_by: Optional["EmployeeType"]

    line_total: Decimal

    @strawberry.field
    def effective_price(self) -> Decimal:
        return self.final_price


# ======================================================
# PAYMENT
# ======================================================

@strawberry.type
class PaymentType:
    id: strawberry.ID
    method: str
    amount: Decimal
    created_at: datetime

    received_by: "EmployeeType"


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

    approved_by: "EmployeeType"


# ======================================================
# POS → INVENTORY STOCK EVENT (AUDIT ONLY)
# ======================================================

@strawberry.type
class POSStockMovementType:
    id: strawberry.ID
    product_id: strawberry.ID
    quantity: Decimal
    created_at: datetime
