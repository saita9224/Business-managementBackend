from asgiref.sync import sync_to_async
from strawberry.dataloader import DataLoader

from .models import Product, StockMovement
from expenses.models import ExpenseItem


# -----------------------------
# Load stock movements by product
# -----------------------------
async def load_movements_by_product(keys: list[int]):
    movements = await sync_to_async(list)(
        StockMovement.objects
        .filter(product_id__in=keys)
        .select_related("expense_item")
        .order_by("created_at")
    )

    grouped = {}
    for m in movements:
        grouped.setdefault(m.product_id, []).append(m)

    return [grouped.get(k, []) for k in keys]



# -----------------------------
# Loader factory (request scoped)
# -----------------------------
def create_dataloaders():
    return {
        "movements_by_product_loader": DataLoader(
            load_fn=load_movements_by_product
        ),
       
    }
