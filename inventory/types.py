from typing import List, Optional
from datetime import datetime

import strawberry
from strawberry.types import Info

from employees.decorators import permission_required
from users.types import UserType


# ============================================================
# EXPENSE LINK TYPE (AUDIT / ACCOUNTABILITY)
# ============================================================
@strawberry.type
class ExpenseLinkType:
    """
    Minimal expense representation linked to stock movements
    for accountability and audit trails.
    """
    id: strawberry.ID
    item_name: str
    total_price: float
    paid_amount: float
    balance: float
    funded_by_business: bool
    created_at: datetime
    performed_by: Optional[UserType]


# ============================================================
# STOCK MOVEMENT TYPE
# ============================================================
@strawberry.type
class StockMovementType:
    """
    Immutable record of stock change.
    """
    id: strawberry.ID
    movement_type: str
    reason: str
    quantity: float
    funded_by_business: bool
    group_id: Optional[str]
    notes: Optional[str]
    created_at: datetime

    expense_item_id: Optional[strawberry.ID]

    # -------------------------------
    # Linked Expense (optional)
    # -------------------------------
    @strawberry.field
    async def expense(self, info: Info) -> Optional[ExpenseLinkType]:
        if not self.expense_item_id:
            return None

        expense = await info.context["expense_loader"].load(self.expense_item_id)
        if not expense:
            return None

        return ExpenseLinkType(
            id=expense.id,
            item_name=expense.item_name,
            total_price=expense.total_price,
            paid_amount=expense.total_price - expense.balance,
            balance=expense.balance,
            funded_by_business=self.funded_by_business,
            created_at=expense.created_at,
            performed_by=expense.performed_by,
        )


# ============================================================
# PRODUCT (INVENTORY ITEM)
# ============================================================
@strawberry.type
class ProductType:
    """
    Inventory Product.
    Current stock is derived from stock movements.
    """
    id: strawberry.ID
    name: str
    category: Optional[str]
    unit: str
    created_at: datetime

    _current_stock: float = strawberry.private()

    # -------------------------------
    # Computed stock (safe)
    # -------------------------------
    @strawberry.field
    def current_stock(self) -> float:
        return self._current_stock

    # -------------------------------
    # Stock movements (permission protected)
    # -------------------------------
    @strawberry.field
    @permission_required("inventory.stock.view")
    async def movements(self, info: Info) -> List[StockMovementType]:
        return await info.context["movements_by_product_loader"].load(self.id)


# ============================================================
# INVENTORY AUDIT TYPE (MANAGEMENT / READ-ONLY)
# ============================================================
@strawberry.type
class InventoryAuditType:
    """
    High-level audit view combining product, movements, and expenses.
    Intended for management, accounting, and compliance.
    """
    product: ProductType
    movements: List[StockMovementType]
