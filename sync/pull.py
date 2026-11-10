# sync/pull.py

from datetime import datetime, timezone
from typing import Dict, Any, Optional

from inventory.models import Product, Category, StockMovement
from POS.models import Receipt, Order, OrderItem, Payment, MenuCategory, MenuItem
from expenses.models import ExpenseItem


def _parse_timestamp(last_pulled_at: Optional[float]) -> Optional[datetime]:
    if not last_pulled_at or last_pulled_at <= 0:
        return None

    # Handle milliseconds vs seconds
    ts_seconds = last_pulled_at / 1000.0 if last_pulled_at > 1e11 else last_pulled_at
    return datetime.fromtimestamp(ts_seconds, tz=timezone.utc)


def _to_epoch_ms(dt: Optional[datetime]) -> Optional[int]:
    if not dt:
        return None
    return int(dt.timestamp() * 1000)


def serialize_product(p: Product) -> Dict[str, Any]:
    return {
        "id": str(p.id),
        "client_id": str(p.client_id) if p.client_id else None,
        "name": p.name,
        "category_id": str(p.category_id) if p.category_id else None,
        "unit": p.unit,
        "current_stock": float(p.current_stock),
        "auto_deduct_on_sale": p.auto_deduct_on_sale,
        "created_at": _to_epoch_ms(p.created_at),
        "updated_at": _to_epoch_ms(p.updated_at),
    }


def serialize_category(c: Category) -> Dict[str, Any]:
    return {
        "id": str(c.id),
        "client_id": str(c.client_id) if c.client_id else None,
        "name": c.name,
        "updated_at": _to_epoch_ms(c.updated_at),
    }


def serialize_menu_category(mc: MenuCategory) -> Dict[str, Any]:
    return {
        "id": str(mc.id),
        "key": mc.key,
        "label": mc.label,
        "created_at": _to_epoch_ms(mc.created_at),
        "updated_at": _to_epoch_ms(mc.updated_at),
    }


def serialize_menu_item(mi: MenuItem) -> Dict[str, Any]:
    return {
        "id": str(mi.id),
        "name": mi.name,
        "category": mi.category,
        "emoji": mi.emoji,
        "price": float(mi.price),
        "product_id": str(mi.product_id) if mi.product_id else None,
        "is_available": mi.is_available,
        "is_pinned": mi.is_pinned,
        "created_at": _to_epoch_ms(mi.created_at),
        "updated_at": _to_epoch_ms(mi.updated_at),
    }


def serialize_receipt(r: Receipt) -> Dict[str, Any]:
    return {
        "id": str(r.id),
        "client_id": str(r.client_id) if r.client_id else None,
        "receipt_number": r.receipt_number,
        "session_id": str(r.session_id),
        "status": r.status,
        "subtotal": float(r.subtotal),
        "total": float(r.total),
        "discount": float(r.discount),
        "table_note": r.table_note,
        "created_at": _to_epoch_ms(r.created_at),
        "updated_at": _to_epoch_ms(r.updated_at),
        "submitted_at": _to_epoch_ms(r.submitted_at),
    }


def serialize_order(o: Order) -> Dict[str, Any]:
    return {
        "id": str(o.id),
        "client_id": str(o.client_id) if o.client_id else None,
        "receipt_id": str(o.receipt_id),
        "created_by_id": str(o.created_by_id) if o.created_by_id else None,
        "created_at": _to_epoch_ms(o.created_at),
    }


def serialize_order_item(oi: OrderItem) -> Dict[str, Any]:
    return {
        "id": str(oi.id),
        "client_id": str(oi.client_id) if oi.client_id else None,
        "order_id": str(oi.order_id),
        "product_id": str(oi.product_id),
        "product_name": oi.product_name,
        "quantity": float(oi.quantity),
        "listed_price": float(oi.listed_price),
        "final_price": float(oi.final_price),
        "line_total": float(oi.line_total),
        "created_at": _to_epoch_ms(oi.created_at),
    }


def serialize_payment(p: Payment) -> Dict[str, Any]:
    return {
        "id": str(p.id),
        "client_id": str(p.client_id) if p.client_id else None,
        "receipt_id": str(p.receipt_id),
        "amount": float(p.amount),
        "method": p.method,
        "created_at": _to_epoch_ms(p.created_at),
    }


def serialize_expense(e: ExpenseItem) -> Dict[str, Any]:
    from django.db.models import Sum
    paid = e.payments.aggregate(total=Sum("amount"))["total"] or 0
    return {
        "id": str(e.id),
        "client_id": str(e.client_id) if e.client_id else None,
        "supplier_id": str(e.supplier_id) if e.supplier_id else None,
        "product_id": str(e.product_id) if e.product_id else None,
        "item_name": e.item_name,
        "quantity": float(e.quantity),
        "unit_price": float(e.unit_price),
        "total_price": float(e.total_price),
        "amount_paid": float(paid),
        "balance": float(e.total_price - paid),
        "is_fully_paid": paid >= e.total_price,
        "supplier_name": e.supplier.name if e.supplier else "",
        "created_at": _to_epoch_ms(e.created_at),
    }


def serialize_stock_movement(sm: StockMovement) -> Dict[str, Any]:
    return {
        "id": str(sm.id),
        "client_id": str(sm.client_id) if sm.client_id else None,
        "product_id": str(sm.product_id),
        "quantity": float(sm.quantity),
        "movement_type": sm.movement_type,
        "reason": sm.reason,
        "notes": sm.notes,
        "created_at": _to_epoch_ms(sm.created_at),
    }


def get_table_changes(model_cls, serializer, since_dt: Optional[datetime], has_updated_at: bool = False) -> Dict[str, Any]:
    if not since_dt:
        all_objs = list(model_cls.objects.all())
        return {
            "created": [serializer(obj) for obj in all_objs],
            "updated": [],
            "deleted": [],
        }

    if has_updated_at:
        created_objs = list(model_cls.objects.filter(created_at__gt=since_dt))
        updated_objs = list(model_cls.objects.filter(updated_at__gt=since_dt, created_at__lte=since_dt))
        return {
            "created": [serializer(obj) for obj in created_objs],
            "updated": [serializer(obj) for obj in updated_objs],
            "deleted": [],
        }
    else:
        created_objs = list(model_cls.objects.filter(created_at__gt=since_dt))
        return {
            "created": [serializer(obj) for obj in created_objs],
            "updated": [],
            "deleted": [],
        }


def extract_pull_changes(last_pulled_at: Optional[float]) -> Dict[str, Any]:
    since_dt = _parse_timestamp(last_pulled_at)

    changes = {
        "products": get_table_changes(Product, serialize_product, since_dt, has_updated_at=True),
        "categories": get_table_changes(Category, serialize_category, since_dt, has_updated_at=True),
        "menu_categories": get_table_changes(MenuCategory, serialize_menu_category, since_dt, has_updated_at=True),
        "menu_items": get_table_changes(MenuItem, serialize_menu_item, since_dt, has_updated_at=True),
        "receipts": get_table_changes(Receipt, serialize_receipt, since_dt, has_updated_at=True),
        "orders": get_table_changes(Order, serialize_order, since_dt, has_updated_at=False),
        "order_items": get_table_changes(OrderItem, serialize_order_item, since_dt, has_updated_at=False),
        "payments": get_table_changes(Payment, serialize_payment, since_dt, has_updated_at=False),
        "expenses": get_table_changes(ExpenseItem, serialize_expense, since_dt, has_updated_at=False),
        "stock_movements": get_table_changes(StockMovement, serialize_stock_movement, since_dt, has_updated_at=False),
    }

    current_timestamp = float(int(datetime.now(timezone.utc).timestamp() * 1000))

    return {
        "changes": changes,
        "timestamp": current_timestamp,
    }
