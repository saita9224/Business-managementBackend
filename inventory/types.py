from typing import List, Optional
import strawberry
from strawberry.types import Info

from .models import InventoryItem
from expenses.models import Expense
from users.types import UserType


@strawberry.type
class ExpenseLinkType:
    """
    Minimal expense representation linked to inventory actions
    for accountability and audit trails.
    """
    id: strawberry.ID
    amount: float
    description: str
    created_at: str
    performed_by: Optional[UserType]


@strawberry.type
class InventoryItemType:
    """
    Inventory GraphQL type.
    Exposes expense linkage for accountability.
    """
    id: strawberry.ID
    name: str
    quantity: float
    unit: str
    created_at: str
    updated_at: str
    created_by: Optional[UserType]
    last_modified_by: Optional[UserType]

    @strawberry.field
    def expenses(self, info: Info) -> List[ExpenseLinkType]:
        """
        All expenses associated with this inventory item.
        Explicitly visible for accountability.
        """
        qs = Expense.objects.filter(inventory_item_id=self.id).select_related(
            "performed_by"
        )
        return [
            ExpenseLinkType(
                id=e.id,
                amount=e.amount,
                description=e.description,
                created_at=e.created_at.isoformat(),
                performed_by=e.performed_by,
            )
            for e in qs
        ]


@strawberry.type
class InventoryAuditType:
    """
    Read-only audit-focused view combining inventory and expense context.
    Useful for managers and finance.
    """
    inventory: InventoryItemType
    expenses: List[ExpenseLinkType]
