# inventory/mutations.py

from typing import Optional, List

import strawberry
from strawberry.types import Info
from graphql import GraphQLError
from asgiref.sync import sync_to_async

from employees.decorators import permission_required

from .models import Product, StockReconciliation, Category
from .queries import wrap_product
from .services import (
    add_stock                  as add_stock_service,
    add_stock_from_expense     as add_stock_from_expense_service,
    remove_stock               as remove_stock_service,
    create_product             as create_product_service,
    create_product_with_stock  as create_product_with_stock_service,
    submit_reconciliation      as submit_reconciliation_service,
    approve_reconciliation     as approve_reconciliation_service,
    reject_reconciliation      as reject_reconciliation_service,
)
from .types import (
    ProductType,
    CategoryType,
    StockMovementType,
    StockReconciliationType,
)


# ============================================================
# INPUT TYPES
# ============================================================

@strawberry.input
class CreateCategoryInput:
    name: str


@strawberry.input
class CreateProductInput:
    name:                str
    unit:                str
    category_id:         Optional[strawberry.ID] = None
    auto_deduct_on_sale: bool = False


@strawberry.input
class CreateProductWithStockInput:
    name:                str
    unit:                str
    category_id:         Optional[strawberry.ID] = None
    quantity:            float
    expense_item_id:     strawberry.ID
    auto_deduct_on_sale: bool = False


@strawberry.input
class AddStockFromExpenseInput:
    product_id:      strawberry.ID
    quantity:        float
    expense_item_id: strawberry.ID


@strawberry.input
class AddStockInput:
    product_id:         strawberry.ID
    quantity:           float
    reason:             str
    funded_by_business: bool
    notes:              Optional[str] = None
    expense_item_id:    Optional[strawberry.ID] = None
    group_id:           Optional[str] = None


@strawberry.input
class RemoveStockInput:
    product_id: strawberry.ID
    quantity:   float
    reason:     str
    notes:      Optional[str] = None


@strawberry.input
class StockCountEntryInput:
    product_id:       strawberry.ID
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
    # CREATE CATEGORY
    # --------------------------------------------------------
    @strawberry.mutation
    @permission_required("inventory.product.create")
    async def create_category(
        self,
        info:  Info,
        input: CreateCategoryInput,
    ) -> CategoryType:

        name = input.name.strip()
        if not name:
            raise GraphQLError("Category name is required")

        def run():
            cat, _ = Category.objects.get_or_create(
                name__iexact=name,
                defaults={"name": name},
            )
            return cat

        try:
            cat = await sync_to_async(run)()
        except Exception as e:
            raise GraphQLError(str(e))

        return CategoryType(id=cat.id, name=cat.name)

    # --------------------------------------------------------
    # CREATE PRODUCT (standalone)
    # category is reloaded with select_related inside the
    # sync block so wrap_product never triggers a lazy DB
    # hit from an async context.
    # --------------------------------------------------------
    @strawberry.mutation
    @permission_required("inventory.product.create")
    async def create_product(
        self,
        info:  Info,
        input: CreateProductInput,
    ) -> ProductType:

        def run():
            category = None
            if input.category_id:
                try:
                    category = Category.objects.get(pk=input.category_id)
                except Category.DoesNotExist:
                    raise ValueError("Category not found")

            product, _ = create_product_service(
                name=input.name,
                unit=input.unit,
                category=category,
                auto_deduct_on_sale=input.auto_deduct_on_sale,
            )

            # Reload with category pre-fetched so wrap_product
            # can access product.category without a lazy DB hit
            # from the async context.
            return (
                Product.objects
                .select_related("category")
                .get(pk=product.pk)
            )

        try:
            product = await sync_to_async(run)()
        except Exception as e:
            raise GraphQLError(str(e))

        stock = await info.context.current_stock_loader.load(product.id)
        return wrap_product(product, float(stock or 0))

    # --------------------------------------------------------
    # CREATE PRODUCT WITH STOCK — ATOMIC
    # Same pattern: reload with select_related inside run().
    # --------------------------------------------------------
    @strawberry.mutation
    @permission_required("inventory.product.create")
    async def create_product_with_stock(
        self,
        info:  Info,
        input: CreateProductWithStockInput,
    ) -> ProductType:

        employee = info.context.user

        def run():
            category = None
            if input.category_id:
                try:
                    category = Category.objects.get(pk=input.category_id)
                except Category.DoesNotExist:
                    raise ValueError("Category not found")

            result = create_product_with_stock_service(
                name=input.name,
                unit=input.unit,
                category=category,
                quantity=input.quantity,
                expense_item_id=int(input.expense_item_id),
                performed_by=employee,
                auto_deduct_on_sale=input.auto_deduct_on_sale,
            )

            # Reload with category pre-fetched
            return (
                Product.objects
                .select_related("category")
                .get(pk=result["product"].pk)
            )

        try:
            product = await sync_to_async(run)()
        except Exception as e:
            raise GraphQLError(str(e))

        stock = await info.context.current_stock_loader.load(product.id)
        return wrap_product(product, float(stock or 0))

    # --------------------------------------------------------
    # ADD STOCK FROM EXPENSE
    # --------------------------------------------------------
    @strawberry.mutation
    @permission_required("inventory.stock.in")
    async def add_stock_from_expense(
        self,
        info:  Info,
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
        info:  Info,
        input: AddStockInput,
    ) -> StockMovementType:

        employee = info.context.user

        try:
            product = await sync_to_async(Product.objects.get)(pk=input.product_id)
        except Product.DoesNotExist:
            raise GraphQLError("Product not found")

        expense_item_id = int(input.expense_item_id) if input.expense_item_id else None

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
        info:  Info,
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
    # SUBMIT RECONCILIATION
    # Products from bulk_create don't have category cached —
    # reload them with select_related before wrap_product.
    # --------------------------------------------------------
    @strawberry.mutation
    @permission_required("inventory.stock.adjust")
    async def submit_reconciliation(
        self,
        info:  Info,
        input: SubmitReconciliationInput,
    ) -> List[StockReconciliationType]:

        employee = info.context.user

        counts = [
            {
                "product_id":       int(entry.product_id),
                "counted_quantity": entry.counted_quantity,
            }
            for entry in input.counts
        ]

        def run():
            reconciliations = submit_reconciliation_service(
                counts=counts,
                counted_by=employee,
            )
            # Reload each reconciliation's product with category
            recon_ids = [r.id for r in reconciliations]
            return list(
                StockReconciliation.objects
                .select_related("product", "product__category", "counted_by")
                .filter(pk__in=recon_ids)
                .order_by("id")
            )

        try:
            reconciliations = await sync_to_async(run)()
        except Exception as e:
            raise GraphQLError(str(e))

        product_ids  = [r.product.id for r in reconciliations]
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
    # refresh_from_db() clears the category cache, so we
    # re-fetch with select_related after the approval.
    # --------------------------------------------------------
    @strawberry.mutation
    @permission_required("inventory.stock.adjust")
    async def approve_reconciliation(
        self,
        info:              Info,
        reconciliation_id: strawberry.ID,
    ) -> StockReconciliationType:

        employee = info.context.user

        def run():
            try:
                recon = StockReconciliation.objects.select_related(
                    "product", "product__category", "counted_by"
                ).get(pk=reconciliation_id)
            except StockReconciliation.DoesNotExist:
                raise ValueError("Reconciliation not found")

            approve_reconciliation_service(
                reconciliation=recon, approved_by=employee,
            )

            # Re-fetch after approval so status + product__category
            # are both fresh and cached
            return StockReconciliation.objects.select_related(
                "product", "product__category", "counted_by"
            ).get(pk=recon.pk)

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
    # Same pattern as approve — re-fetch with select_related.
    # --------------------------------------------------------
    @strawberry.mutation
    @permission_required("inventory.stock.adjust")
    async def reject_reconciliation(
        self,
        info:              Info,
        reconciliation_id: strawberry.ID,
        notes:             Optional[str] = None,
    ) -> StockReconciliationType:

        employee = info.context.user

        def run():
            try:
                recon = StockReconciliation.objects.select_related(
                    "product", "product__category", "counted_by"
                ).get(pk=reconciliation_id)
            except StockReconciliation.DoesNotExist:
                raise ValueError("Reconciliation not found")

            reject_reconciliation_service(
                reconciliation=recon, approved_by=employee, notes=notes,
            )

            # Re-fetch with category cached
            return StockReconciliation.objects.select_related(
                "product", "product__category", "counted_by"
            ).get(pk=recon.pk)

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