import strawberry
from datetime import date
from typing import Optional, List


# ------------------------------------------------------------
# SUPPLIER TYPE
# ------------------------------------------------------------
@strawberry.type
class SupplierType:
    id: strawberry.ID
    name: str
    phone: Optional[str]
    email: Optional[str]
    address: Optional[str]


# ------------------------------------------------------------
# PAYMENT TYPE
# ------------------------------------------------------------
@strawberry.type
class ExpensePaymentType:
    id: strawberry.ID
    expense_id: int
    amount: float
    paid_at: date


# ------------------------------------------------------------
# EXPENSE ITEM TYPE
# ------------------------------------------------------------
@strawberry.type
class ExpenseItemType:
    id: strawberry.ID
    supplier: Optional[SupplierType]
    product_id: Optional[int]

    item_name: str

    unit_price: float           # matches Django model
    quantity: float
    total_price: float          # matches Django model

    balance: float              # computed property on model
    payment_group_id: str
    created_at: date

    payments: List[ExpensePaymentType]


# ------------------------------------------------------------
# EXPENSE DETAILS TYPE  (FIX FOR GraphQL ERROR)
# ------------------------------------------------------------
@strawberry.type
class ExpenseDetailsType:
    expense: ExpenseItemType
    payments: List[ExpensePaymentType]
    remaining_balance: float


# ------------------------------------------------------------
# INPUT TYPES
# ------------------------------------------------------------
@strawberry.input
class ExpenseInput:
    supplier_id: Optional[int]
    product_id: Optional[int]
    item_name: str
    quantity: float
    unit_price: float


@strawberry.input
class PayBalanceInput:
    expense_id: int
    amount: float
