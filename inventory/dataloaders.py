from collections import defaultdict
from typing import List, Dict, Optional

from asgiref.sync import sync_to_async
from django.db.models import (
    Sum,
    Q,
    OuterRef,
    Subquery,
    F,
)
from strawberry.dataloader import DataLoader

from .models import Product, StockMovement, StockReconciliation


# ────────────────────────────────────────────────
# Load stock movements by product (audit trail)
# ────────────────────────────────────────────────
async def load_movements_by_product(
    keys: List[int],
) -> List[List[StockMovement]]:
    movements = await sync_to_async(list)(
        StockMovement.objects
        .filter(product_id__in=keys)
        .select_related("expense_item", "performed_by")
        .order_by("created_at")
    )

    grouped: Dict[int, List[StockMovement]] = defaultdict(list)
    for movement in movements:
        grouped[movement.product_id].append(movement)

    # DataLoader requires output order to match input keys
    return [grouped.get(product_id, []) for product_id in keys]


# ────────────────────────────────────────────────
# Load current stock per product (derived, safe)
# ────────────────────────────────────────────────
async def load_current_stock(
    keys: List[int],
) -> List[int]:
    """
    Stock is derived from movements:
    - IN  → increase
    - OUT → decrease
    """

    rows = await sync_to_async(list)(
        StockMovement.objects
        .filter(product_id__in=keys)
        .values("product_id")
        .annotate(
            total_in=Sum(
                "quantity",
                filter=Q(movement_type=StockMovement.IN),
            ),
            total_out=Sum(
                "quantity",
                filter=Q(movement_type=StockMovement.OUT),
            ),
        )
    )

    stock_map: Dict[int, int] = {}
    for row in rows:
        stock_map[row["product_id"]] = (
            (row["total_in"] or 0) - (row["total_out"] or 0)
        )

    return [stock_map.get(product_id, 0) for product_id in keys]


# ────────────────────────────────────────────────
# Load latest reconciliation per product (safe)
# ────────────────────────────────────────────────
async def load_latest_reconciliation(
    keys: List[int],
) -> List[Optional[StockReconciliation]]:
    """
    Uses a Subquery to guarantee exactly ONE
    latest reconciliation per product.
    """

    latest_reconciliation_subquery = (
        StockReconciliation.objects
        .filter(product_id=OuterRef("product_id"))
        .order_by("-counted_at")
        .values("id")[:1]
    )

    reconciliations = await sync_to_async(list)(
        StockReconciliation.objects
        .filter(product_id__in=keys)
        .annotate(
            latest_id=Subquery(latest_reconciliation_subquery)
        )
        .filter(id=F("latest_id"))
        .select_related("counted_by", "approved_by")
    )

    recon_map: Dict[int, StockReconciliation] = {
        recon.product_id: recon
        for recon in reconciliations
    }

    return [recon_map.get(product_id) for product_id in keys]


# ────────────────────────────────────────────────
# Loader factory (request-scoped)
# ────────────────────────────────────────────────
def create_inventory_dataloaders():
    """
    Must be created per request to ensure:
    - Correct caching
    - No data leakage across users
    """
    return {
        "movements_by_product_loader": DataLoader(
            load_fn=load_movements_by_product
        ),
        "current_stock_loader": DataLoader(
            load_fn=load_current_stock
        ),
        "latest_reconciliation_loader": DataLoader(
            load_fn=load_latest_reconciliation
        ),
    }
