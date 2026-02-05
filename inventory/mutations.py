from typing import Optional

import strawberry
from strawberry.types import Info
from graphql import GraphQLError
from asgiref.sync import sync_to_async

from employees.decorators import permission_required

from .models import Product
from .services import (
    add_stock as add_stock_service,
    remove_stock as remove_stock_service,
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

        employee = info.context.user

        def create():
            return Product.objects.create(
                name=input.name,
                unit=input.unit,
                category=input.category,
            )

        return await sync_to_async(create)()


    # --------------------------------------------------------
    # ADD STOCK (IN)
    # --------------------------------------------------------
    @strawberry.mutation
    @permission_required("inventory.stock.in")
    async def add_stock(
        self,
        info: Info,
        input: AddStockInput,
    ) -> StockMovementType:

        employee = info.context.user

        try:
            product = await sync_to_async(Product.objects.get)(
                pk=input.product_id
            )
        except Product.DoesNotExist:
            raise GraphQLError("Product not found")

        return await sync_to_async(add_stock_service)(
            product=product,
            quantity=input.quantity,
            reason=input.reason,
            funded_by_business=input.funded_by_business,
            expense_item=input.expense_item_id,
            group_id=input.group_id,
            notes=input.notes,
            performed_by=employee,
        )


    # --------------------------------------------------------
    # REMOVE STOCK (OUT)
    # --------------------------------------------------------
    @strawberry.mutation
    @permission_required("inventory.stock.out")
    async def remove_stock(
        self,
        info: Info,
        input: RemoveStockInput,
    ) -> StockMovementType:

        employee = info.context.user

        try:
            product = await sync_to_async(Product.objects.get)(
                pk=input.product_id
            )
        except Product.DoesNotExist:
            raise GraphQLError("Product not found")

        return await sync_to_async(remove_stock_service)(
            product=product,
            quantity=input.quantity,
            reason=input.reason,
            notes=input.notes,
            performed_by=employee,
        )
