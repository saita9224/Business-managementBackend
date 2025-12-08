from asgiref.sync import sync_to_async
from strawberry.dataloader import DataLoader

from .models import ExpenseItem, Supplier, ExpensePayment
from inventory.models import Product


async def load_suppliers(keys: list[int]):
    suppliers = await sync_to_async(list)(
        Supplier.objects.filter(id__in=keys)
    )
    result = {s.id: s for s in suppliers}
    return [result.get(k) for k in keys]


async def load_products(keys: list[int]):
    products = await sync_to_async(list)(
        Product.objects.filter(id__in=keys)
    )
    result = {p.id: p for p in products}
    return [result.get(k) for k in keys]


async def load_payments(keys: list[int]):
    payments = await sync_to_async(list)(
        ExpensePayment.objects.filter(expense_id__in=keys).order_by("paid_at")
    )
    grouped = {}
    for p in payments:
        grouped.setdefault(p.expense_id, []).append(p)
    return [grouped.get(k, []) for k in keys]


async def load_expenses_by_supplier(keys: list[int]):
    items = await sync_to_async(list)(
        ExpenseItem.objects.filter(supplier_id__in=keys)
    )
    grouped = {}
    for e in items:
        grouped.setdefault(e.supplier_id, []).append(e)
    return [grouped.get(k, []) for k in keys]


def create_dataloaders():
    return {
        "supplier_loader": DataLoader(load_fn=load_suppliers),
        "product_loader": DataLoader(load_fn=load_products),
        "payments_by_expense_loader": DataLoader(load_fn=load_payments),
        "expenses_by_supplier_loader": DataLoader(load_fn=load_expenses_by_supplier),
    }
