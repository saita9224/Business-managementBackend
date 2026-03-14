# POS/types.py

from typing import List, Optional
from datetime import datetime, date
from decimal import Decimal

import strawberry
from strawberry.types import Info
from asgiref.sync import sync_to_async

from employees.types import EmployeeType

from .models import (
    POSSession,
    Receipt,
    Order,
    OrderItem,
    Payment,
    CreditAccount,
    POSStockMovement,
    MenuItem,
)


@strawberry.type
class MenuItemType:
    id: strawberry.ID
    name: str
    emoji: str
    price: Decimal
    is_available: bool
    is_pinned: bool
    product_id: Optional[strawberry.ID]

    @strawberry.field
    def has_inventory(self) -> bool:
        return self.product_id is not None


@strawberry.type
class POSSessionType:
    id: strawberry.ID
    opened_at: datetime
    closed_at: Optional[datetime]
    opening_cash: Decimal
    closing_cash: Optional[Decimal]
    is_active: bool

    @strawberry.field
    async def employee(self, info: Info) -> EmployeeType:
        return await sync_to_async(lambda: self.employee)()

    @strawberry.field
    async def receipts(self, info: Info) -> List["ReceiptType"]:
        return await info.context.receipts_by_session.load(int(self.id))


@strawberry.type
class ReceiptType:
    id: strawberry.ID
    receipt_number: str
    subtotal: Decimal
    discount: Decimal
    total: Decimal
    status: str
    table_note: str
    created_at: datetime
    submitted_at: Optional[datetime]

    @strawberry.field
    async def created_by(self, info: Info) -> EmployeeType:
        return await sync_to_async(lambda: self.created_by)()

    @strawberry.field
    async def session(self, info: Info) -> POSSessionType:
        return await sync_to_async(lambda: self.session)()

    @strawberry.field
    async def orders(self, info: Info) -> List["OrderType"]:
        return await info.context.orders_by_receipt.load(int(self.id))

    @strawberry.field
    async def payments(self, info: Info) -> List["PaymentType"]:
        return await info.context.payments_by_receipt.load(int(self.id))

    @strawberry.field
    async def credit(self, info: Info) -> Optional["CreditAccountType"]:
        return await info.context.credit_by_receipt.load(int(self.id))

    @strawberry.field
    async def stock_movements(self, info: Info) -> List["POSStockMovementType"]:
        return await info.context.stock_by_receipt.load(int(self.id))

    @strawberry.field
    async def balance(self, info: Info) -> Decimal:
        payments = await info.context.payments_by_receipt.load(int(self.id))
        paid = sum(p.amount for p in payments)
        return self.total - paid


@strawberry.type
class OrderType:
    id: strawberry.ID
    is_saved: bool
    is_refunded: bool
    created_at: datetime

    @strawberry.field
    async def created_by(self, info: Info) -> EmployeeType:
        return await sync_to_async(lambda: self.created_by)()

    @strawberry.field
    async def items(self, info: Info) -> List["OrderItemType"]:
        return await info.context.items_by_order.load(int(self.id))


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
    line_total: Decimal

    @strawberry.field
    async def price_override_by(self, info: Info) -> Optional[EmployeeType]:
        return await sync_to_async(lambda: self.price_override_by)()

    @strawberry.field
    def effective_price(self) -> Decimal:
        return self.final_price


@strawberry.type
class PaymentType:
    id: strawberry.ID
    method: str
    amount: Decimal
    created_at: datetime

    @strawberry.field
    async def received_by(self, info: Info) -> EmployeeType:
        return await sync_to_async(lambda: self.received_by)()


@strawberry.type
class CreditAccountType:
    id: strawberry.ID
    customer_name: str
    customer_phone: Optional[str]
    credit_amount: Decimal
    due_date: date
    is_settled: bool
    settled_at: Optional[datetime]

    @strawberry.field
    async def approved_by(self, info: Info) -> EmployeeType:
        return await sync_to_async(lambda: self.approved_by)()

    @strawberry.field
    async def settled_by(self, info: Info) -> Optional[EmployeeType]:
        return await sync_to_async(lambda: self.settled_by)()


@strawberry.type
class POSStockMovementType:
    id: strawberry.ID
    product_id: strawberry.ID
    quantity: Decimal
    deducted_from_inventory: bool
    notes: Optional[str]
    created_at: datetime