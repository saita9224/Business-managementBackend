# expenses/types.py

import strawberry
from datetime import datetime
from typing import Optional, List
from decimal import Decimal
from graphql import GraphQLError

from inventory.types import ProductType


# ============================================================
# SUPPLIER TYPE
# ============================================================

@strawberry.type
class SupplierType:
    id: strawberry.ID
    name: str
    phone: Optional[str]
    email: Optional[str]
    address: Optional[str]
    created_at: datetime


# ============================================================
# PAYMENT TYPE
# ============================================================

@strawberry.type
class ExpensePaymentType:
    id: strawberry.ID
    expense_id: int
    amount: Decimal
    paid_at: datetime


# ============================================================
# EXPENSE ITEM TYPE
# ============================================================

@strawberry.type
class ExpenseItemType:
    id: strawberry.ID

    supplier_id: Optional[int]
    product_id: Optional[int]

    item_name: str
    unit_price: Decimal
    quantity: Decimal
    total_price: Decimal

    amount_paid: Decimal
    balance: Decimal
    is_fully_paid: bool

    payment_group_id: str
    created_at: datetime

    # --------------------------------------------------------
    # Supplier
    # --------------------------------------------------------
    @strawberry.field
    async def supplier(self, info) -> Optional[SupplierType]:
        if not self.supplier_id:
            return None
        return await info.context["supplier_loader"].load(self.supplier_id)

    # --------------------------------------------------------
    # Product
    # --------------------------------------------------------
    @strawberry.field
    async def product(self, info) -> Optional[ProductType]:
        if not self.product_id:
            return None
        return await info.context["product_loader"].load(self.product_id)

    # --------------------------------------------------------
    # Payments (RBAC Protected)
    # --------------------------------------------------------
    @strawberry.field
    async def payments(self, info) -> List[ExpensePaymentType]:
        user = info.context.user

        if not user or not user.is_authenticated:
            raise GraphQLError("Authentication required")

        if not user.has_permission("expenses.view_payments"):
            raise GraphQLError("Permission denied: expenses.view_payments")

        return await info.context["payments_by_expense_loader"].load(self.id)


# ============================================================
# EXPENSE DETAILS TYPE
# ============================================================

@strawberry.type
class ExpenseDetailsType:
    expense: ExpenseItemType
    payments: List[ExpensePaymentType]
    remaining_balance: Decimal


# ============================================================
# INPUT TYPES (HYBRID ALIGNED)
# ============================================================

@strawberry.input
class ExpenseInput:
    supplier_id: Optional[int]        # ✅ supported
    supplier_name: Optional[str]      # ✅ supported

    product_id: Optional[int]
    item_name: str
    quantity: Decimal
    unit_price: Decimal


@strawberry.input
class PayBalanceInput:
    expense_id: int
    amount: Decimal