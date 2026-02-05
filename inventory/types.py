from typing import List, Optional
from datetime import datetime

import strawberry
from strawberry.types import Info
from strawberry import Private
from graphql import GraphQLError

from employees.types import EmployeeType


# ============================================================
# RBAC HELPERS
# ============================================================

def require_auth(info: Info):
    employee = info.context.user
    if not employee or not employee.is_authenticated:
        raise GraphQLError("Authentication required")
    return employee


def require_permission(employee, perm: str):
    if not employee.has_permission(perm):
        raise GraphQLError(f"Permission denied: {perm}")


# ============================================================
# EXPENSE LINK TYPE (AUDIT / ACCOUNTABILITY)
# ============================================================

@strawberry.type
class ExpenseLinkType:
    id: strawberry.ID
    item_name: str
    total_price: float
    paid_amount: float
    balance: float
    funded_by_business: bool
    created_at: datetime
    performed_by: Optional[EmployeeType]


# ============================================================
# STOCK MOVEMENT TYPE (IMMUTABLE LEDGER)
# ============================================================

@strawberry.type
class StockMovementType:
    id: strawberry.ID
    movement_type: str  # IN / OUT / ADJUSTMENT
    reason: str
    quantity: float
    group_id: Optional[str]
    notes: Optional[str]
    created_at: datetime

    expense_item_id: Optional[strawberry.ID]
    performed_by: Optional[EmployeeType]

    # --------------------------------------------------------
    # PRIVATE INTERNAL FIELD (NOT IN GRAPHQL SCHEMA)
    # --------------------------------------------------------
    _funded_by_business: Private[Optional[bool]]

    # --------------------------------------------------------
    # Business funding (IN only)
    # --------------------------------------------------------
    @strawberry.field
    def funded_by_business(self) -> Optional[bool]:
        if self.movement_type == "IN":
            return self._funded_by_business
        return None

    # --------------------------------------------------------
    # Linked Expense (STRICT RBAC)
    # --------------------------------------------------------
    @strawberry.field
    async def expense(self, info: Info) -> Optional[ExpenseLinkType]:
        employee = require_auth(info)
        require_permission(employee, "expenses.view_expense")

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
            funded_by_business=self._funded_by_business or False,
            created_at=expense.created_at,
            performed_by=expense.performed_by,
        )


# ============================================================
# PRODUCT
# ============================================================

@strawberry.type
class ProductType:
    id: strawberry.ID
    name: str
    category: Optional[str]
    unit: str
    created_at: datetime

    # --------------------------------------------------------
    # PRIVATE FIELD
    # --------------------------------------------------------
    _current_stock: Private[float]

    # --------------------------------------------------------
    # Current stock (RBAC)
    # --------------------------------------------------------
    @strawberry.field
    def current_stock(self, info: Info) -> float:
        employee = require_auth(info)
        require_permission(employee, "inventory.view_stock")
        return self._current_stock

    # --------------------------------------------------------
    # Movements (STRICT RBAC)
    # --------------------------------------------------------
    @strawberry.field
    async def movements(self, info: Info) -> List[StockMovementType]:
        employee = require_auth(info)
        require_permission(employee, "inventory.view_movements")

        return await info.context["movements_by_product_loader"].load(self.id)


# ============================================================
# STOCK RECONCILIATION (COUNT & ADJUSTMENT WORKFLOW)
# ============================================================

@strawberry.type
class StockReconciliationType:
    id: strawberry.ID
    product: ProductType
    expected_quantity: float
    counted_quantity: float
    difference: float
    status: str
    counted_at: datetime
    counted_by: Optional[EmployeeType]
    notes: Optional[str]


# ============================================================
# INVENTORY AUDIT VIEW
# ============================================================

@strawberry.type
class InventoryAuditType:
    product: ProductType
    movements: List[StockMovementType]
