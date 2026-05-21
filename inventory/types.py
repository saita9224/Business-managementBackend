# inventory/types.py

from typing import List, Optional
from datetime import datetime

import strawberry
from strawberry.types import Info
from strawberry import Private
from graphql import GraphQLError

from employees.types import EmployeeType


def require_auth(info: Info):
    employee = info.context.user
    if not employee or not employee.is_authenticated:
        raise GraphQLError("Authentication required")
    return employee


# ============================================================
# CATEGORY TYPE
# ============================================================

@strawberry.type
class CategoryType:
    id:   strawberry.ID
    name: str


# ============================================================
# CATEGORY SUGGESTION TYPE
# ============================================================

@strawberry.type
class CategorySuggestionType:
    category:             CategoryType
    matched_product_name: str


# ============================================================
# EXPENSE LINK TYPE
# ============================================================

@strawberry.type
class ExpenseLinkType:
    id:                 strawberry.ID
    item_name:          str
    total_price:        float
    funded_by_business: bool
    created_at:         datetime


# ============================================================
# STOCK MOVEMENT TYPE
# ============================================================

@strawberry.type
class StockMovementType:
    id:            strawberry.ID
    movement_type: str
    reason:        str
    quantity:      float
    group_id:      Optional[str]
    notes:         Optional[str]
    created_at:    datetime

    expense_item_id: Optional[strawberry.ID]
    performed_by:    Optional[EmployeeType]

    _funded_by_business: Private[Optional[bool]]

    @strawberry.field
    def funded_by_business(self) -> Optional[bool]:
        if self.movement_type == "IN":
            return self._funded_by_business
        return None

    @strawberry.field
    async def expense(self, info: Info) -> Optional[ExpenseLinkType]:
        require_auth(info)
        if not self.expense_item_id:
            return None
        expense = await info.context.expense_loader.load(
            int(self.expense_item_id)
        )
        if not expense:
            return None
        return ExpenseLinkType(
            id=expense.id,
            item_name=expense.item_name,
            total_price=float(expense.total_price),
            funded_by_business=self._funded_by_business or False,
            created_at=expense.created_at,
        )


# ============================================================
# PRODUCT TYPE
# ============================================================

@strawberry.type
class ProductType:
    id:                  strawberry.ID
    name:                str
    unit:                str
    auto_deduct_on_sale: bool
    created_at:          datetime

    # category is now a CategoryType object, not a plain string
    category: Optional[CategoryType]

    _current_stock: Private[float]

    @strawberry.field
    def current_stock(self, info: Info) -> float:
        require_auth(info)
        return self._current_stock

    @strawberry.field
    async def movements(self, info: Info) -> List[StockMovementType]:
        require_auth(info)
        return await info.context.movements_by_product_loader.load(
            int(self.id)
        )


# ============================================================
# STOCK RECONCILIATION TYPE
# ============================================================

@strawberry.type
class StockReconciliationType:
    id:               strawberry.ID
    product:          ProductType
    system_quantity:  float
    counted_quantity: float
    difference:       float
    status:           str
    counted_at:       datetime
    counted_by:       Optional[EmployeeType]
    notes:            Optional[str]


# ============================================================
# INVENTORY AUDIT VIEW
# ============================================================

@strawberry.type
class InventoryAuditType:
    product:   ProductType
    movements: List[StockMovementType]