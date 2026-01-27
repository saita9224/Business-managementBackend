from typing import Optional

import strawberry
from strawberry.types import Info

from employees.decorators import permission_required

from .services import (
    create_product,
    add_stock,
    remove_stock,
)
from .types import ProductType, StockMovementType


# ============================================================
# INPUT TYPES
# ============================================================

@strawberry.input
class CreateProductInput:
    name: str
    unit: str
    category: Optional[str] = None


@strawberry.input
class AddStockInput:
    product_id: strawberry.ID
    quantity: float
    reason: str
    funded_by_business: bool
    notes: Optional[str] = None

    # Optional expense linkage
    expense_item_id: Optional[strawberry.ID] = None
    group_id: Optional[str] = None


@strawberry.input
class RemoveStockInput:
    product_id: strawberry.ID
    quantity: float
    reason: str
    notes: Optional[str] = None


# ============================================================
# MUTATIONS
# ============================================================

@strawberry.type
class InventoryMutation:

    # --------------------------------------------------------
    # CREATE PRODUCT
    # --------------------------------------------------------
    @strawberry.mutation
    @permission_required("inventory.product.create")
    async def create_product(
        self,
        info: Info,
        input: CreateProductInput,
    ) -> ProductType:

        user = info.context.user

        product = await create_product(
            name=input.name,
            unit=input.unit,
            category=input.category,
            performed_by=user,
        )

        return product


    # --------------------------------------------------------
    # ADD STOCK (INBOUND)
    # --------------------------------------------------------
    @strawberry.mutation
    @permission_required("inventory.stock.in")
    async def add_stock(
        self,
        info: Info,
        input: AddStockInput,
    ) -> StockMovementType:

        user = info.context.user

        movement = await add_stock(
            product_id=input.product_id,
            quantity=input.quantity,
            reason=input.reason,
            funded_by_business=input.funded_by_business,
            notes=input.notes,
            expense_item_id=input.expense_item_id,
            group_id=input.group_id,
            performed_by=user,
        )

        return movement


    # --------------------------------------------------------
    # REMOVE STOCK (OUTBOUND)
    # --------------------------------------------------------
    @strawberry.mutation
    @permission_required("inventory.stock.out")
    async def remove_stock(
        self,
        info: Info,
        input: RemoveStockInput,
    ) -> StockMovementType:

        user = info.context.user

        movement = await remove_stock(
            product_id=input.product_id,
            quantity=input.quantity,
            reason=input.reason,
            notes=input.notes,
            performed_by=user,
        )

        return movement
