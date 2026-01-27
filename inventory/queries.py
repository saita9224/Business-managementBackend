from typing import List, Optional

import strawberry
from strawberry.types import Info
from asgiref.sync import sync_to_async

from employees.decorators import permission_required

from .models import Product, StockMovement, StockReconciliation
from .types import (
    ProductType,
    StockMovementType,
    InventoryAuditType,
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

        return await sync_to_async(fetch)()


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

        try:
            return await sync_to_async(Product.objects.get)(pk=id)
        except Product.DoesNotExist:
            raise ValueError("Product not found")


    # --------------------------------------------------------
    # GLOBAL STOCK MOVEMENTS (AUDIT VIEW)
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
    # INVENTORY AUDIT (MANAGEMENT)
    # --------------------------------------------------------
    @strawberry.field
    @permission_required("inventory.stock.view_history")
    async def inventory_audit(
        self,
        info: Info,
        product_id: strawberry.ID,
    ) -> InventoryAuditType:

        try:
            product = await sync_to_async(Product.objects.get)(pk=product_id)
        except Product.DoesNotExist:
            raise ValueError("Product not found")

        movements = await info.context[
            "movements_by_product_loader"
        ].load(product.id)

        return InventoryAuditType(
            product=product,
            movements=movements,
        )


    # --------------------------------------------------------
    # PENDING STOCK RECONCILIATIONS (PHYSICAL COUNTS)
    # --------------------------------------------------------
    @strawberry.field
    @permission_required("inventory.stock.adjust")
    async def pending_reconciliations(
        self,
        info: Info,
    ) -> List[StockReconciliation]:

        def fetch():
            return list(
                StockReconciliation.objects
                .filter(status=StockReconciliation.PENDING)
                .select_related("product", "counted_by")
                .order_by("-counted_at")
            )

        return await sync_to_async(fetch)()
