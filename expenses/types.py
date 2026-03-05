# expenses/types.py

import strawberry
from datetime import datetime
from typing import Optional, List
from decimal import Decimal

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

    payment_group_id: str
    created_at: datetime

    # --------------------------------------------------------
    # Supplier
    # --------------------------------------------------------

    @strawberry.field
    async def supplier(self, info) -> Optional[SupplierType]:
        """
        Resolve supplier using DataLoader
        """
        if not self.supplier_id:
            return None

        loader = info.context["supplier_loader"]
        return await loader.load(self.supplier_id)

    # --------------------------------------------------------
    # Product
    # --------------------------------------------------------

    @strawberry.field
    async def product(self, info) -> Optional[ProductType]:
        """
        Resolve product using DataLoader
        """
        if not self.product_id:
            return None

        loader = info.context["product_loader"]
        return await loader.load(self.product_id)

    # --------------------------------------------------------
    # Payments
    # --------------------------------------------------------

    @strawberry.field
    async def payments(self, info) -> List[ExpensePaymentType]:
        """
        Resolve payments using DataLoader
        """
        loader = info.context["payments_by_expense_loader"]
        return await loader.load(self.id)

    # --------------------------------------------------------
    # Amount Paid
    # --------------------------------------------------------

    @strawberry.field
    async def amount_paid(self, info) -> Decimal:
        """
        Calculate total amount paid for this expense
        """
        loader = info.context["payments_by_expense_loader"]
        payments = await loader.load(self.id)

        return sum((p.amount for p in payments), Decimal("0"))

    # --------------------------------------------------------
    # Balance
    # --------------------------------------------------------

    @strawberry.field
    async def balance(self, info) -> Decimal:
        """
        Remaining unpaid balance
        """
        loader = info.context["payments_by_expense_loader"]
        payments = await loader.load(self.id)

        amount_paid = sum((p.amount for p in payments), Decimal("0"))

        return self.total_price - amount_paid

    # --------------------------------------------------------
    # Is Fully Paid
    # --------------------------------------------------------

    @strawberry.field
    async def is_fully_paid(self, info) -> bool:
        """
        Whether expense is fully paid
        """
        loader = info.context["payments_by_expense_loader"]
        payments = await loader.load(self.id)

        amount_paid = sum((p.amount for p in payments), Decimal("0"))

        return amount_paid >= self.total_price


# ============================================================
# EXPENSE DETAILS TYPE
# ============================================================

@strawberry.type
class ExpenseDetailsType:
    expense: ExpenseItemType
    payments: List[ExpensePaymentType]
    remaining_balance: Decimal


# ============================================================
# INPUT TYPES
# ============================================================

@strawberry.input
class ExpenseInput:
    """
    Hybrid supplier input.

    Supports either:
    - existing supplier via supplier_id
    - new supplier via supplier_name
    """

    supplier_id: Optional[int]
    supplier_name: Optional[str]

    product_id: Optional[int]

    item_name: str
    quantity: Decimal
    unit_price: Decimal


@strawberry.input
class PayBalanceInput:
    expense_id: int
    amount: Decimal