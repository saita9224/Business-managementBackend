# expenses/types.py

import strawberry
from datetime import date
from typing import Optional, List

# Django models (only used for field access)
from .models import ExpenseItem
from inventory.models import Product
from graphql import GraphQLError


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
# PRODUCT TYPE (for resolver return)
# ------------------------------------------------------------
@strawberry.type
class ProductType:
    id: strawberry.ID
    name: str
    buying_price: float
    selling_price: float
    stock: float
    created_at: date


# ------------------------------------------------------------
# EXPENSE ITEM TYPE (DATALOADER ENABLED)
# ------------------------------------------------------------
@strawberry.type
class ExpenseItemType:
    id: strawberry.ID

    # required for resolvers to access them
    supplier_id: Optional[int]
    product_id: Optional[int]

    item_name: str
    unit_price: float
    quantity: float
    total_price: float

    balance: float
    payment_group_id: str
    created_at: date

    # -------------------------------
    # Supplier via dataloader
    # -------------------------------
    @strawberry.field
    async def supplier(self, info) -> Optional[SupplierType]:
        if not self.supplier_id:
            return None
        return await info.context["supplier_loader"].load(self.supplier_id)

    # -------------------------------
    # Product via dataloader
    # -------------------------------
    @strawberry.field
    async def product(self, info) -> Optional[ProductType]:
        if not self.product_id:
            return None
        return await info.context["product_loader"].load(self.product_id)

    # -------------------------------
    # Payments list via dataloader
    # -------------------------------
    @strawberry.field
    async def payments(self, info) -> List[ExpensePaymentType]:
        user = info.context.user

        if not user.is_authenticated:
            raise GraphQLError("Authentication required.")

        if not user.has_permission("expenses.view_payments"):
            raise GraphQLError("Permission denied: expenses.view_payments")

        return await info.context["payments_by_expense_loader"].load(self.id)


# ------------------------------------------------------------
# EXPENSE DETAILS TYPE
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
