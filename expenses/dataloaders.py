# expenses/dataloaders.py

from decimal import Decimal
from typing import List, Dict

from asgiref.sync import sync_to_async
from strawberry.dataloader import DataLoader
from django.db.models import Sum

from .models import ExpenseItem, Supplier, ExpensePayment
from inventory.models import Product


# ==========================================================
# SUPPLIER LOADER
# ==========================================================

async def load_suppliers(keys: List[int]) -> List[Supplier]:

    suppliers = await sync_to_async(list)(
        Supplier.objects.filter(id__in=keys)
    )

    supplier_map: Dict[int, Supplier] = {
        supplier.id: supplier for supplier in suppliers
    }

    return [supplier_map.get(k) for k in keys]


# ==========================================================
# PRODUCT LOADER
# ==========================================================

async def load_products(keys: List[int]) -> List[Product]:

    products = await sync_to_async(list)(
        Product.objects.filter(id__in=keys).select_related("category")
    )

    product_map: Dict[int, Product] = {
        product.id: product for product in products
    }

    return [product_map.get(k) for k in keys]


# ==========================================================
# EXPENSE ITEM LOADER
# Single-object lookup used by StockMovementType.expense
# ==========================================================

async def load_expense_items(keys: List[int]) -> List[ExpenseItem]:

    items = await sync_to_async(list)(
        ExpenseItem.objects.filter(id__in=keys)
    )

    item_map: Dict[int, ExpenseItem] = {
        item.id: item for item in items
    }

    return [item_map.get(k) for k in keys]


# ==========================================================
# PAYMENTS BY EXPENSE
# ==========================================================

async def load_payments(keys: List[int]) -> List[List[ExpensePayment]]:

    payments = await sync_to_async(list)(
        ExpensePayment.objects
        .filter(expense_id__in=keys)
        .select_related("expense", "expense__supplier")
        .order_by("paid_at")
    )

    grouped: Dict[int, List[ExpensePayment]] = {}

    for payment in payments:
        grouped.setdefault(payment.expense_id, []).append(payment)

    return [grouped.get(k, []) for k in keys]


# ==========================================================
# EXPENSES BY SUPPLIER
# ==========================================================

async def load_expenses_by_supplier(keys: List[int]) -> List[List[ExpenseItem]]:

    items = await sync_to_async(list)(
        ExpenseItem.objects
        .filter(supplier_id__in=keys)
        .select_related("supplier", "related_product")
    )

    grouped: Dict[int, List[ExpenseItem]] = {}

    for item in items:
        grouped.setdefault(item.supplier_id, []).append(item)

    return [grouped.get(k, []) for k in keys]


# ==========================================================
# PAYMENT TOTALS (AGGREGATION LOADER)
# ==========================================================

async def load_payment_totals(keys: List[int]) -> List[Decimal]:

    rows = await sync_to_async(list)(
        ExpensePayment.objects
        .filter(expense_id__in=keys)
        .values("expense_id")
        .annotate(total=Sum("amount"))
    )

    totals_map: Dict[int, Decimal] = {
        row["expense_id"]: row["total"] or Decimal("0.00")
        for row in rows
    }

    return [totals_map.get(k, Decimal("0.00")) for k in keys]


# ==========================================================
# CREATE LOADERS
# ==========================================================

def create_expenses_dataloaders():

    return {

        # supplier lookup
        "supplier_loader":
            DataLoader(load_fn=load_suppliers),

        # product lookup
        "product_loader":
            DataLoader(load_fn=load_products),

        # payments for each expense
        "payments_by_expense_loader":
            DataLoader(load_fn=load_payments),

        # expenses belonging to supplier
        "expenses_by_supplier_loader":
            DataLoader(load_fn=load_expenses_by_supplier),

        # aggregated payment totals
        "payment_total_loader":
            DataLoader(load_fn=load_payment_totals),

        # single expense item lookup
        "expense_loader":
            DataLoader(load_fn=load_expense_items),
    }
