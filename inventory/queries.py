from typing import List, Optional

import strawberry
from strawberry.types import Info
from graphql import GraphQLError

from .models import Product, StockMovement
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
    async def products(
        self,
        info: Info,
        search: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[ProductType]:

        user = info.context.user

        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        if not user.has_permission("inventory.view_product"):
            raise GraphQLError("Permission denied: inventory.view_product")

        qs = Product.objects.all().order_by("name")

        if search:
            qs = qs.filter(name__icontains=search)

        if category:
            qs = qs.filter(category=category)

        return qs


    # --------------------------------------------------------
    # SINGLE PRODUCT (DETAIL VIEW)
    # --------------------------------------------------------
    @strawberry.field
    async def product(
        self,
        info: Info,
        id: strawberry.ID,
    ) -> ProductType:

        user = info.context.user

        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        if not user.has_permission("inventory.view_product"):
            raise GraphQLError("Permission denied: inventory.view_product")

        try:
            return Product.objects.get(pk=id)
        except Product.DoesNotExist:
            raise GraphQLError("Product not found")


    # --------------------------------------------------------
    # STOCK MOVEMENTS (GLOBAL VIEW)
    # --------------------------------------------------------
    @strawberry.field
    async def stock_movements(
        self,
        info: Info,
        product_id: Optional[strawberry.ID] = None,
    ) -> List[StockMovementType]:

        user = info.context.user

        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        if not user.has_permission("inventory.view_movements"):
            raise GraphQLError("Permission denied: inventory.view_movements")

        qs = StockMovement.objects.select_related(
            "product",
            "expense_item",
        ).order_by("-created_at")

        if product_id:
            qs = qs.filter(product_id=product_id)

        return qs


    # --------------------------------------------------------
    # INVENTORY AUDIT (MANAGEMENT VIEW)
    # --------------------------------------------------------
    @strawberry.field
    async def inventory_audit(
        self,
        info: Info,
        product_id: strawberry.ID,
    ) -> InventoryAuditType:

        user = info.context.user

        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        if not user.has_permission("inventory.view_audit"):
            raise GraphQLError("Permission denied: inventory.view_audit")

        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            raise GraphQLError("Product not found")

        movements = StockMovement.objects.filter(
            product_id=product_id
        ).order_by("created_at")

        return InventoryAuditType(
            product=product,
            movements=movements,
        )
