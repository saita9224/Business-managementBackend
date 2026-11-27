# inventory/queries.py

from typing import List, Optional
import asyncio

import strawberry
from strawberry.types import Info
from graphql import GraphQLError
from asgiref.sync import sync_to_async

from employees.decorators import permission_required

from .models import Product, StockMovement, StockMovementReason, StockReconciliation, Category
from .types import (
    ProductType,
    CategoryType,
    CategorySuggestionType,
    StockMovementType,
    StockMovementReasonType,
    InventoryAuditType,
    StockReconciliationType,
)


# ============================================================
# HELPER
# ============================================================

def wrap_product(product: Product, current_stock: float) -> ProductType:
    return ProductType(
        id=product.id,
        name=product.name,
        category=(
            CategoryType(id=product.category.id, name=product.category.name)
            if product.category else None
        ),
        unit=product.unit,
        auto_deduct_on_sale=product.auto_deduct_on_sale,
        cost_per_unit=(
            float(product.cost_per_unit)
            if product.cost_per_unit is not None
            else None
        ),
        created_at=product.created_at,
        _current_stock=current_stock,
    )


# ============================================================
# QUERIES
# ============================================================

@strawberry.type
class InventoryQuery:

    # --------------------------------------------------------
    # LIST ALL CATEGORIES
    # --------------------------------------------------------
    @strawberry.field
    @permission_required("inventory.product.view")
    async def categories(self, info: Info) -> List[CategoryType]:
        cats = await sync_to_async(list)(
            Category.objects.all().order_by("name")
        )
        return [CategoryType(id=c.id, name=c.name) for c in cats]

    # --------------------------------------------------------
    # SUGGEST CATEGORY BY PRODUCT NAME
    # Fires when the user has typed 3+ characters in the
    # item name field. Returns the category of the first
    # existing product whose name contains the search term.
    # Frontend uses this to auto-select the category tile.
    # --------------------------------------------------------
    @strawberry.field
    @permission_required("inventory.product.view")
    async def suggest_category(
        self,
        info:         Info,
        product_name: str,
    ) -> Optional[CategorySuggestionType]:

        if not product_name or len(product_name.strip()) < 3:
            return None

        def fetch():
            return (
                Product.objects
                .filter(
                    name__icontains=product_name.strip(),
                    category__isnull=False,
                )
                .select_related("category")
                .first()
            )

        product = await sync_to_async(fetch)()

        if not product:
            return None

        return CategorySuggestionType(
            category=CategoryType(
                id=product.category.id,
                name=product.category.name,
            ),
            matched_product_name=product.name,
        )

    # --------------------------------------------------------
    # LIST PRODUCTS
    # --------------------------------------------------------
    @strawberry.field
    @permission_required("inventory.product.view")
    async def products(
        self,
        info:     Info,
        search:   Optional[str] = None,
        category: Optional[str] = None,
        limit:    Optional[int] = None,
        offset:   int = 0,
    ) -> List[ProductType]:

        def fetch():
            qs = (
                Product.objects
                .select_related("category")
                .order_by("name")
            )
            if search:
                qs = qs.filter(name__icontains=search)
            if category:
                qs = qs.filter(category__name__iexact=category)
            if limit is not None:
                return list(qs[offset: offset + min(limit, 1000)])
            if offset:
                return list(qs[offset:])
            return list(qs)

        products = await sync_to_async(fetch)()
        if not products:
            return []

        product_ids  = [p.id for p in products]
        stock_values = await info.context.current_stock_loader.load_many(product_ids)

        return [
            wrap_product(p, float(stock or 0))
            for p, stock in zip(products, stock_values)
        ]

    # --------------------------------------------------------
    # SINGLE PRODUCT
    # --------------------------------------------------------
    @strawberry.field
    @permission_required("inventory.product.view")
    async def product(
        self,
        info: Info,
        id:   strawberry.ID,
    ) -> ProductType:

        def fetch():
            try:
                return (
                    Product.objects
                    .select_related("category")
                    .get(pk=id)
                )
            except Product.DoesNotExist:
                return None

        product = await sync_to_async(fetch)()
        if product is None:
            raise GraphQLError("Product not found")

        stock = await info.context.current_stock_loader.load(product.id)
        return wrap_product(product, float(stock or 0))

    # --------------------------------------------------------
    # STOCK MOVEMENTS
    # --------------------------------------------------------
    @strawberry.field
    @permission_required("inventory.stock.view")
    async def stock_movements(
        self,
        info:       Info,
        product_id: Optional[strawberry.ID] = None,
        limit:      Optional[int] = None,
        offset:     int = 0,
    ) -> List[StockMovementType]:

        def fetch():
            qs = (
                StockMovement.objects
                .select_related("product", "expense_item", "performed_by", "reason")
                .order_by("-created_at")
            )
            if product_id:
                qs = qs.filter(product_id=product_id)
            if limit is not None:
                return list(qs[offset: offset + min(limit, 1000)])
            if offset:
                return list(qs[offset:])
            return list(qs)

        return await sync_to_async(fetch)()

    # --------------------------------------------------------
    # INVENTORY AUDIT
    # --------------------------------------------------------
    @strawberry.field
    @permission_required("inventory.stock.view_history")
    async def inventory_audit(
        self,
        info:       Info,
        product_id: strawberry.ID,
    ) -> InventoryAuditType:

        def fetch():
            try:
                return (
                    Product.objects
                    .select_related("category")
                    .get(pk=product_id)
                )
            except Product.DoesNotExist:
                return None

        product = await sync_to_async(fetch)()
        if product is None:
            raise GraphQLError("Product not found")

        stock, movements = await asyncio.gather(
            info.context.current_stock_loader.load(product.id),
            info.context.movements_by_product_loader.load(product.id),
        )

        return InventoryAuditType(
            product=wrap_product(product, float(stock or 0)),
            movements=movements,
        )

    # --------------------------------------------------------
    # PENDING RECONCILIATIONS
    # --------------------------------------------------------
    @strawberry.field
    @permission_required("inventory.stock.adjust")
    async def pending_reconciliations(
        self,
        info: Info,
    ) -> List[StockReconciliationType]:

        def fetch():
            return list(
                StockReconciliation.objects
                .filter(status=StockReconciliation.PENDING)
                .select_related("product", "product__category", "counted_by")
                .order_by("-counted_at")
            )

        reconciliations = await sync_to_async(fetch)()
        if not reconciliations:
            return []

        product_ids  = [r.product.id for r in reconciliations]
        stock_values = await info.context.current_stock_loader.load_many(product_ids)

        return [
            StockReconciliationType(
                id=r.id,
                product=wrap_product(r.product, float(stock or 0)),
                system_quantity=r.system_quantity,
                counted_quantity=r.counted_quantity,
                difference=r.counted_quantity - r.system_quantity,
                status=r.status,
                counted_at=r.counted_at,
                counted_by=r.counted_by,
                notes=r.notes,
            )
            for r, stock in zip(reconciliations, stock_values)
        ]

    # --------------------------------------------------------
    # STOCK MOVEMENT REASONS
    # --------------------------------------------------------
    @strawberry.field
    @permission_required("inventory.stock.view")
    async def stock_movement_reasons(
        self,
        info: Info,
        active_only: bool = True,
        direction: Optional[str] = None,  # "IN", "OUT", or None for both
    ) -> List[StockMovementReasonType]:
        """
        Get all stock movement reasons for the current tenant.
        """
        def fetch():
            qs = StockMovementReason.objects.all()
            if active_only:
                qs = qs.filter(is_active=True)
            if direction == "IN":
                qs = qs.filter(applies_to_in=True)
            elif direction == "OUT":
                qs = qs.filter(applies_to_out=True)
            return list(qs.order_by("sort_order", "name"))
        
        reasons = await sync_to_async(fetch)()
        return [
            StockMovementReasonType(
                id=r.id,
                code=r.code,
                name=r.name,
                applies_to_in=r.applies_to_in,
                applies_to_out=r.applies_to_out,
                requires_expense=r.requires_expense,
                is_sale_related=r.is_sale_related,
                requires_verification=r.requires_verification,
                verification_permission=r.verification_permission,
                category=r.category,
                consumption_type=r.consumption_type,
                sort_order=r.sort_order,
                is_system=r.is_system,
                is_active=r.is_active,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in reasons
        ]

    # --------------------------------------------------------
    # SINGLE STOCK MOVEMENT REASON
    # --------------------------------------------------------
    @strawberry.field
    @permission_required("inventory.stock.view")
    async def stock_movement_reason(
        self,
        info: Info,
        id: strawberry.ID,
    ) -> StockMovementReasonType:
        """
        Get a single stock movement reason by ID.
        """
        def fetch():
            try:
                return StockMovementReason.objects.get(pk=id)
            except StockMovementReason.DoesNotExist:
                return None
        
        reason = await sync_to_async(fetch)()
        if reason is None:
            raise GraphQLError("Stock movement reason not found")
        
        return StockMovementReasonType(
            id=reason.id,
            code=reason.code,
            name=reason.name,
            applies_to_in=reason.applies_to_in,
            applies_to_out=reason.applies_to_out,
            requires_expense=reason.requires_expense,
            is_sale_related=reason.is_sale_related,
            requires_verification=reason.requires_verification,
            verification_permission=reason.verification_permission,
            category=reason.category,
            consumption_type=reason.consumption_type,
            sort_order=reason.sort_order,
            is_system=reason.is_system,
            is_active=reason.is_active,
            created_at=reason.created_at,
            updated_at=reason.updated_at,
        )