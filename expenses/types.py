# expenses/types.py

import strawberry
from datetime import datetime
from typing import Optional, List
from decimal import Decimal

from strawberry import Private


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

    @strawberry.field
    def item_name(self) -> str:
        return self.expense.item_name

    @strawberry.field
    def supplier_name(self) -> Optional[str]:
        return self.expense.supplier.name if self.expense.supplier else None

    @strawberry.field
    def expense_total(self) -> Decimal:
        return self.expense.total_price


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
        if not self.supplier_id:
            return None
        return await info.context.supplier_loader.load(self.supplier_id)

    # --------------------------------------------------------
    # Product — uses wrap_product to populate _current_stock
    # --------------------------------------------------------
    @strawberry.field
    async def product(self, info) -> Optional["InventoryProductType"]:
        if not self.product_id:
            return None

        from inventory.queries import wrap_product  # avoid circular import

        product = await info.context.product_loader.load(self.product_id)
        if not product:
            return None

        stock = await info.context.current_stock_loader.load(product.id)
        return wrap_product(product, float(stock or 0))

    # --------------------------------------------------------
    # Payments
    # --------------------------------------------------------
    @strawberry.field
    async def payments(self, info) -> List[ExpensePaymentType]:
        return await info.context.payments_by_expense_loader.load(self.id)

    # --------------------------------------------------------
    # Amount Paid
    # --------------------------------------------------------
    @strawberry.field
    async def amount_paid(self, info) -> Decimal:
        payments = await info.context.payments_by_expense_loader.load(self.id)
        return sum((p.amount for p in payments), Decimal("0"))

    # --------------------------------------------------------
    # Balance
    # --------------------------------------------------------
    @strawberry.field
    async def balance(self, info) -> Decimal:
        payments = await info.context.payments_by_expense_loader.load(self.id)
        amount_paid = sum((p.amount for p in payments), Decimal("0"))
        return self.total_price - amount_paid

    # --------------------------------------------------------
    # Is Fully Paid
    # --------------------------------------------------------
    @strawberry.field
    async def is_fully_paid(self, info) -> bool:
        payments = await info.context.payments_by_expense_loader.load(self.id)
        amount_paid = sum((p.amount for p in payments), Decimal("0"))
        return amount_paid >= self.total_price


# ============================================================
# CREATE EXPENSE RESULT
# ============================================================

@strawberry.type
class InventoryProductType:
    id: strawberry.ID
    name: str
    unit: str
    current_stock: float


@strawberry.type
class CreateExpenseResult:
    expense: ExpenseItemType
    matched_product: Optional[InventoryProductType]


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