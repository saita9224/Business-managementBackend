# inventory/mutations.py

from typing import Optional, List

import strawberry
from strawberry.types import Info
from graphql import GraphQLError
from asgiref.sync import sync_to_async

from employees.decorators import permission_required

from .models import Product, StockReconciliation
from .queries import wrap_product
from .services import (
    add_stock as add_stock_service,
    add_stock_from_expense as add_stock_from_expense_service,
    remove_stock as remove_stock_service,
    create_product_with_stock as create_product_with_stock_service,
    submit_reconciliation as submit_reconciliation_service,
    approve_reconciliation as approve_reconciliation_service,
    reject_reconciliation as reject_reconciliation_service,
)
from .types import ProductType, StockMovementType, StockReconciliationType


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


@strawberry.input
class StockCountEntryInput:
    product_id: strawberry.ID
    counted_quantity: float


@strawberry.input
class SubmitReconciliationInput:
    counts: List[StockCountEntryInput]


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
    # CREATE PRODUCT WITH STOCK — ATOMIC
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
    # ADD STOCK FROM EXPENSE — ATOMIC
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


    # --------------------------------------------------------
    # SUBMIT STOCK RECONCILIATION (BULK)
    # Creates PENDING reconciliation records for manager review.
    # --------------------------------------------------------
    @strawberry.mutation
    @permission_required("inventory.stock.adjust")
    async def submit_reconciliation(
        self,
        info: Info,
        input: SubmitReconciliationInput,
    ) -> List[StockReconciliationType]:

        employee = info.context.user

        counts = [
            {
                "product_id": int(entry.product_id),
                "counted_quantity": entry.counted_quantity,
            }
            for entry in input.counts
        ]

        try:
            reconciliations = await sync_to_async(submit_reconciliation_service)(
                counts=counts,
                counted_by=employee,
            )
        except Exception as e:
            raise GraphQLError(str(e))

        # Resolve current stock for each product after submission
        product_ids = [r.product.id for r in reconciliations]
        stock_values = await info.context.current_stock_loader.load_many(product_ids)

        return [
            StockReconciliationType(
                id=r.id,
                product=wrap_product(r.product, float(stock or 0)),
                system_quantity=r.system_quantity,
                counted_quantity=r.counted_quantity,
                difference=r.difference,
                status=r.status,
                counted_at=r.counted_at,
                counted_by=r.counted_by,
                notes=r.notes,
            )
            for r, stock in zip(reconciliations, stock_values)
        ]


    # --------------------------------------------------------
    # APPROVE RECONCILIATION
    # Fires an ADJUSTMENT stock movement if difference != 0.
    # --------------------------------------------------------
    @strawberry.mutation
    @permission_required("inventory.stock.adjust")
    async def approve_reconciliation(
        self,
        info: Info,
        reconciliation_id: strawberry.ID,
    ) -> StockReconciliationType:

        employee = info.context.user

        def run():
            try:
                recon = StockReconciliation.objects.select_related(
                    "product", "counted_by"
                ).get(pk=reconciliation_id)
            except StockReconciliation.DoesNotExist:
                raise ValueError("Reconciliation not found")

            approve_reconciliation_service(
                reconciliation=recon,
                approved_by=employee,
            )
            recon.refresh_from_db()
            return recon

        try:
            recon = await sync_to_async(run)()
        except Exception as e:
            raise GraphQLError(str(e))

        stock = await info.context.current_stock_loader.load(recon.product.id)

        return StockReconciliationType(
            id=recon.id,
            product=wrap_product(recon.product, float(stock or 0)),
            system_quantity=recon.system_quantity,
            counted_quantity=recon.counted_quantity,
            difference=recon.difference,
            status=recon.status,
            counted_at=recon.counted_at,
            counted_by=recon.counted_by,
            notes=recon.notes,
        )


    # --------------------------------------------------------
    # REJECT RECONCILIATION
    # --------------------------------------------------------
    @strawberry.mutation
    @permission_required("inventory.stock.adjust")
    async def reject_reconciliation(
        self,
        info: Info,
        reconciliation_id: strawberry.ID,
        notes: Optional[str] = None,
    ) -> StockReconciliationType:

        employee = info.context.user

        def run():
            try:
                recon = StockReconciliation.objects.select_related(
                    "product", "counted_by"
                ).get(pk=reconciliation_id)
            except StockReconciliation.DoesNotExist:
                raise ValueError("Reconciliation not found")

            reject_reconciliation_service(
                reconciliation=recon,
                approved_by=employee,
                notes=notes,
            )
            recon.refresh_from_db()
            return recon

        try:
            recon = await sync_to_async(run)()
        except Exception as e:
            raise GraphQLError(str(e))

        stock = await info.context.current_stock_loader.load(recon.product.id)

        return StockReconciliationType(
            id=recon.id,
            product=wrap_product(recon.product, float(stock or 0)),
            system_quantity=recon.system_quantity,
            counted_quantity=recon.counted_quantity,
            difference=recon.difference,
            status=recon.status,
            counted_at=recon.counted_at,
            counted_by=recon.counted_by,
            notes=recon.notes,
        )