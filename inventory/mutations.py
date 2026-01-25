from typing import Optional

import strawberry
from strawberry.types import Info
from graphql import GraphQLError

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
    async def create_product(
        self,
        info: Info,
        input: CreateProductInput,
    ) -> ProductType:

        user = info.context.user

        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        if not user.has_permission("inventory.create_product"):
            raise GraphQLError("Permission denied: inventory.create_product")

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
    async def add_stock(
        self,
        info: Info,
        input: AddStockInput,
    ) -> StockMovementType:

        user = info.context.user

        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        if not user.has_permission("inventory.add_stock"):
            raise GraphQLError("Permission denied: inventory.add_stock")

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
    async def remove_stock(
        self,
        info: Info,
        input: RemoveStockInput,
    ) -> StockMovementType:

        user = info.context.user

        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        if not user.has_permission("inventory.remove_stock"):
            raise GraphQLError("Permission denied: inventory.remove_stock")

        movement = await remove_stock(
            product_id=input.product_id,
            quantity=input.quantity,
            reason=input.reason,
            notes=input.notes,
            performed_by=user,
        )

        return movement
