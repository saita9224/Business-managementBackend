# inventory/mutations.py

from typing import Optional

import strawberry
from strawberry.types import Info
from graphql import GraphQLError
from asgiref.sync import sync_to_async

from employees.decorators import permission_required

from .models import Product
from .queries import wrap_product
from .services import (
    add_stock as add_stock_service,
    add_stock_from_expense as add_stock_from_expense_service,
    remove_stock as remove_stock_service,
    create_product_with_stock as create_product_with_stock_service,
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
class CreateProductWithStockInput:
    name: str
    unit: str
    category: Optional[str] = None
    quantity: float
    expense_item_id: strawberry.ID


@strawberry.input
class AddStockFromExpenseInput:
    product_id: strawberry.ID
    quantity: float
    expense_item_id: strawberry.ID


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
    # CREATE PRODUCT (standalone — no stock)
    # --------------------------------------------------------
    @strawberry.mutation
    @permission_required("inventory.product.create")
    async def create_product(
        self,
        info: Info,
        input: CreateProductInput,
    ) -> ProductType:

        def get_or_create():
            product, _ = Product.objects.get_or_create(
                name__iexact=input.name,
                defaults={
                    "name": input.name,
                    "unit": input.unit,
                    "category": input.category,
                },
            )
            return product

        product = await sync_to_async(get_or_create)()
        stock = await info.context.current_stock_loader.load(product.id)
        return wrap_product(product, float(stock or 0))


    # --------------------------------------------------------
    # CREATE PRODUCT WITH STOCK — ATOMIC (new product flow)
    # Used when expense is created for an item not in inventory.
    # Product + stock movement written in one transaction.
    # --------------------------------------------------------
    @strawberry.mutation
    @permission_required("inventory.product.create")
    async def create_product_with_stock(
        self,
        info: Info,
        input: CreateProductWithStockInput,
    ) -> ProductType:

        employee = info.context.user

        def run():
            return create_product_with_stock_service(
                name=input.name,
                unit=input.unit,
                category=input.category,
                quantity=input.quantity,
                expense_item_id=int(input.expense_item_id),
                performed_by=employee,
            )

        try:
            result = await sync_to_async(run)()
        except Exception as e:
            raise GraphQLError(str(e))

        product = result["product"]
        stock = await info.context.current_stock_loader.load(product.id)
        return wrap_product(product, float(stock or 0))


    # --------------------------------------------------------
    # ADD STOCK FROM EXPENSE — ATOMIC (matched product flow)
    # Used when expense matches an existing inventory product.
    # Stock movement + expense link written in one transaction.
    # --------------------------------------------------------
    @strawberry.mutation
    @permission_required("inventory.stock.in")
    async def add_stock_from_expense(
        self,
        info: Info,
        input: AddStockFromExpenseInput,
    ) -> StockMovementType:

        employee = info.context.user

        try:
            return await sync_to_async(add_stock_from_expense_service)(
                product_id=int(input.product_id),
                quantity=input.quantity,
                expense_item_id=int(input.expense_item_id),
                performed_by=employee,
            )
        except Exception as e:
            raise GraphQLError(str(e))


    # --------------------------------------------------------
    # ADD STOCK (IN) — general purpose
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
            product = await sync_to_async(Product.objects.get)(pk=input.product_id)
        except Product.DoesNotExist:
            raise GraphQLError("Product not found")

        expense_item_id = (
            int(input.expense_item_id) if input.expense_item_id else None
        )

        try:
            return await sync_to_async(add_stock_service)(
                product=product,
                quantity=input.quantity,
                reason=input.reason,
                funded_by_business=input.funded_by_business,
                expense_item_id=expense_item_id,
                group_id=input.group_id,
                notes=input.notes,
                performed_by=employee,
            )
        except Exception as e:
            raise GraphQLError(str(e))


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
            product = await sync_to_async(Product.objects.get)(pk=input.product_id)
        except Product.DoesNotExist:
            raise GraphQLError("Product not found")

        try:
            return await sync_to_async(remove_stock_service)(
                product=product,
                quantity=input.quantity,
                reason=input.reason,
                notes=input.notes,
                performed_by=employee,
            )
        except Exception as e:
            raise GraphQLError(str(e))