from asgiref.sync import sync_to_async
from django.db.models import Sum, Max
from strawberry.dataloader import DataLoader

from .models import Product, StockMovement, StockReconciliation


# ────────────────────────────────────────────────
# Load stock movements by product
# ────────────────────────────────────────────────
async def load_movements_by_product(keys: list[int]):
    movements = await sync_to_async(list)(
        StockMovement.objects
        .filter(product_id__in=keys)
        .select_related("expense_item", "performed_by")
        .order_by("created_at")
    )

    grouped = {}
    for m in movements:
        grouped.setdefault(m.product_id, []).append(m)

    return [grouped.get(k, []) for k in keys]


# ────────────────────────────────────────────────
# Load current stock per product (derived)
# ────────────────────────────────────────────────
async def load_current_stock(keys: list[int]):
    rows = await sync_to_async(list)(
        StockMovement.objects
        .filter(product_id__in=keys)
        .values("product_id", "movement_type")
        .annotate(total=Sum("quantity"))
    )

    stock_map = {}

    for row in rows:
        pid = row["product_id"]
        stock_map.setdefault(pid, 0)

        if row["movement_type"] == StockMovement.IN:
            stock_map[pid] += row["total"]
        else:
            stock_map[pid] -= row["total"]

    return [stock_map.get(k, 0) for k in keys]


# ────────────────────────────────────────────────
# Load latest reconciliation per product
# ────────────────────────────────────────────────
async def load_latest_reconciliation(keys: list[int]):
    latest = await sync_to_async(list)(
        StockReconciliation.objects
        .filter(product_id__in=keys)
        .values("product_id")
        .annotate(latest=Max("counted_at"))
    )

    latest_map = {
        row["product_id"]: row["latest"]
        for row in latest
    }

    reconciliations = await sync_to_async(list)(
        StockReconciliation.objects
        .filter(
            product_id__in=latest_map.keys(),
            counted_at__in=latest_map.values()
        )
        .select_related("counted_by", "approved_by")
    )

    recon_map = {
        r.product_id: r for r in reconciliations
    }

    return [recon_map.get(k) for k in keys]


# ────────────────────────────────────────────────
# Loader factory (request scoped)
# ────────────────────────────────────────────────
def create_inventory_dataloaders():
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
