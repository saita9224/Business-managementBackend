# inventory/queries.py

from typing import List, Optional
import asyncio

import strawberry
from strawberry.types import Info
from graphql import GraphQLError
from asgiref.sync import sync_to_async

from employees.decorators import permission_required

from .models import Product, StockMovement, StockReconciliation
from .types import (
    ProductType,
    StockMovementType,
    InventoryAuditType,
    StockReconciliationType,
)


# ============================================================
# HELPER — wraps a Product + resolved stock into ProductType
# ============================================================

def wrap_product(product: Product, current_stock: float) -> ProductType:
    return ProductType(
        id=product.id,
        name=product.name,
        category=product.category,
        unit=product.unit,
        created_at=product.created_at,
        _current_stock=current_stock,   # 👈 this was missing — causes the crash
    )


# ============================================================
# INVENTORY QUERIES
# ============================================================

@strawberry.type
class InventoryQuery:

    # --------------------------------------------------------
    # LIST PRODUCTS
    # --------------------------------------------------------
    @strawberry.field
    @permission_required("inventory.product.view")
    async def products(
        self,
        info: Info,
        search: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[ProductType]:

        def fetch():
            qs = Product.objects.all().order_by("name")
            if search:
                qs = qs.filter(name__icontains=search)
            if category:
                qs = qs.filter(category=category)
            return list(qs)

        products = await sync_to_async(fetch)()

        if not products:
            return []

        product_ids = [p.id for p in products]
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
        id: strawberry.ID,
    ) -> ProductType:

        def fetch():
            try:
                return Product.objects.get(pk=id)
            except Product.DoesNotExist:
                return None

        product = await sync_to_async(fetch)()
        if product is None:
            raise GraphQLError("Product not found")

        stock = await info.context.current_stock_loader.load(product.id)
        return wrap_product(product, float(stock or 0))


    # --------------------------------------------------------
    # GLOBAL STOCK MOVEMENTS (AUDIT)
    # --------------------------------------------------------
    @strawberry.field
    @permission_required("inventory.stock.view")
    async def stock_movements(
        self,
        info: Info,
        product_id: Optional[strawberry.ID] = None,
    ) -> List[StockMovementType]:

        def fetch():
            qs = (
                StockMovement.objects
                .select_related("product", "expense_item", "performed_by")
                .order_by("-created_at")
            )
            if product_id:
                qs = qs.filter(product_id=product_id)
            return list(qs)

        return await sync_to_async(fetch)()


    # --------------------------------------------------------
    # INVENTORY AUDIT
    # --------------------------------------------------------
    @strawberry.field
    @permission_required("inventory.stock.view_history")
    async def inventory_audit(
        self,
        info: Info,
        product_id: strawberry.ID,
    ) -> InventoryAuditType:

        def fetch():
            try:
                return Product.objects.get(pk=product_id)
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
    # PENDING STOCK RECONCILIATIONS
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
                .select_related("product", "counted_by")
                .order_by("-counted_at")
            )

        reconciliations = await sync_to_async(fetch)()

        if not reconciliations:
            return []

        product_ids = [r.product.id for r in reconciliations]
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