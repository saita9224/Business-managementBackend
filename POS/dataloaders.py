# pos/dataloaders.py

from asgiref.sync import sync_to_async
from strawberry.dataloader import DataLoader

from .models import (
    POSSession,
    Receipt,
    Order,
    OrderItem,
    Payment,
    CreditAccount,
    POSStockMovement,
)

# ======================================================
# RECEIPTS BY SESSION
# ======================================================
async def load_receipts_by_session(keys: list[int]):
    receipts = await sync_to_async(list)(
        Receipt.objects
        .filter(session_id__in=keys)
        .select_related("session", "created_by")
        .order_by("-created_at")
    )

    grouped = {}
    for r in receipts:
        grouped.setdefault(r.session_id, []).append(r)

    return [grouped.get(k, []) for k in keys]


# ======================================================
# ORDERS BY RECEIPT
# ======================================================
async def load_orders_by_receipt(keys: list[int]):
    orders = await sync_to_async(list)(
        Order.objects
        .filter(receipt_id__in=keys)
        .select_related("created_by")
        .order_by("created_at")
    )

    grouped = {}
    for o in orders:
        grouped.setdefault(o.receipt_id, []).append(o)

    return [grouped.get(k, []) for k in keys]


# ======================================================
# ITEMS BY ORDER
# ======================================================
async def load_items_by_order(keys: list[int]):
    items = await sync_to_async(list)(
        OrderItem.objects
        .filter(order_id__in=keys)
        .select_related("price_override_by")
    )

    grouped = {}
    for i in items:
        grouped.setdefault(i.order_id, []).append(i)

    return [grouped.get(k, []) for k in keys]


# ======================================================
# PAYMENTS BY RECEIPT
# ======================================================
async def load_payments_by_receipt(keys: list[int]):
    payments = await sync_to_async(list)(
        Payment.objects
        .filter(receipt_id__in=keys)
        .select_related("received_by")
        .order_by("created_at")
    )

    grouped = {}
    for p in payments:
        grouped.setdefault(p.receipt_id, []).append(p)

    return [grouped.get(k, []) for k in keys]


# ======================================================
# CREDIT BY RECEIPT (ONE-TO-ONE)
# ======================================================
async def load_credit_by_receipt(keys: list[int]):
    credits = await sync_to_async(list)(
        CreditAccount.objects
        .filter(receipt_id__in=keys)
        .select_related("approved_by")
    )

    mapped = {c.receipt_id: c for c in credits}
    return [mapped.get(k) for k in keys]


# ======================================================
# STOCK EMISSIONS BY RECEIPT (AUDIT ONLY)
# ======================================================
async def load_stock_by_receipt(keys: list[int]):
    movements = await sync_to_async(list)(
        POSStockMovement.objects
        .filter(receipt_id__in=keys)
        .order_by("created_at")
    )

    grouped = {}
    for m in movements:
        grouped.setdefault(m.receipt_id, []).append(m)

    return [grouped.get(k, []) for k in keys]


# ======================================================
# LOADER FACTORY (REQUEST SCOPED)
# ======================================================
def create_pos_dataloaders():
    return {
        "receipts_by_session": DataLoader(load_receipts_by_session),
        "orders_by_receipt": DataLoader(load_orders_by_receipt),
        "items_by_order": DataLoader(load_items_by_order),
        "payments_by_receipt": DataLoader(load_payments_by_receipt),
        "credit_by_receipt": DataLoader(load_credit_by_receipt),
        "stock_by_receipt": DataLoader(load_stock_by_receipt),
    }
