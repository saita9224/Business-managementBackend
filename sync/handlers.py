# sync/handlers.py

from typing import Dict, Any, Tuple
from django.core.exceptions import ValidationError

from employees.models import Employee
from POS.models import Receipt, POSSession, MenuItem, OrderItem, Payment
from POS.services import (
    create_receipt as svc_create_receipt,
    create_order as svc_create_order,
    add_order_item as svc_add_order_item,
    add_menu_order_item as svc_add_menu_order_item,
    submit_order as svc_submit_order,
    accept_payment as svc_accept_payment,
)
from expenses.services import create_expense_item as svc_create_expense_item
from inventory.models import Product
from inventory.services import (
    add_stock as svc_add_stock,
    remove_stock as svc_remove_stock,
)


def handle_create_receipt(
    user: Employee, payload: Dict[str, Any], client_id: str
) -> Tuple[bool, Dict[str, Any]]:
    session_id = payload.get("session_id")
    if not session_id:
        raise ValidationError("session_id is required in payload")

    try:
        session = POSSession.objects.get(pk=int(session_id), is_active=True)
    except POSSession.DoesNotExist:
        raise ValidationError(f"Active session with ID {session_id} not found")

    receipt, created = svc_create_receipt(
        session=session,
        created_by=user,
        discount=payload.get("discount", 0),
        table_note=payload.get("table_note", ""),
        client_id=client_id,
    )

    return created, {
        "receipt_id": receipt.id,
        "receipt_number": receipt.receipt_number,
        "status": receipt.status,
    }


def handle_create_order(
    user: Employee, payload: Dict[str, Any], client_id: str
) -> Tuple[bool, Dict[str, Any]]:
    receipt_id = payload.get("receipt_id")
    if not receipt_id:
        raise ValidationError("receipt_id is required in payload")

    try:
        receipt = Receipt.objects.get(pk=int(receipt_id))
    except Receipt.DoesNotExist:
        raise ValidationError(f"Receipt with ID {receipt_id} not found")

    order, created = svc_create_order(
        receipt=receipt,
        created_by=user,
        client_id=client_id,
    )

    return created, {
        "order_id": order.id,
        "receipt_id": order.receipt_id,
    }


def handle_add_order_item(
    user: Employee, payload: Dict[str, Any], client_id: str
) -> Tuple[bool, Dict[str, Any]]:
    from POS.models import Order

    existing = OrderItem.objects.filter(client_id=client_id).first()
    if existing:
        return False, {
            "order_item_id": existing.id,
            "order_id": existing.order_id,
            "line_total": str(existing.line_total),
        }

    order_id = payload.get("order_id")
    product_id = payload.get("product_id")
    if not order_id or not product_id:
        raise ValidationError("order_id and product_id are required in payload")

    try:
        order = Order.objects.get(pk=int(order_id))
    except Order.DoesNotExist:
        raise ValidationError(f"Order with ID {order_id} not found")

    try:
        product = Product.objects.get(pk=int(product_id))
    except Product.DoesNotExist:
        raise ValidationError(f"Product with ID {product_id} not found")

    item = svc_add_order_item(
        order=order,
        product=product,
        quantity=payload.get("quantity", 1),
        final_price=payload.get("final_price", 0),
        sold_by=user,
        price_override_reason=payload.get("price_override_reason"),
        client_id=client_id,
    )

    return True, {
        "order_item_id": item.id,
        "order_id": item.order_id,
        "line_total": str(item.line_total),
    }


def handle_add_menu_order_item(
    user: Employee, payload: Dict[str, Any], client_id: str
) -> Tuple[bool, Dict[str, Any]]:
    from POS.models import Order

    existing = OrderItem.objects.filter(client_id=client_id).first()
    if existing:
        return False, {
            "order_item_id": existing.id,
            "order_id": existing.order_id,
            "line_total": str(existing.line_total),
        }

    order_id = payload.get("order_id")
    menu_item_id = payload.get("menu_item_id")
    if not order_id or not menu_item_id:
        raise ValidationError("order_id and menu_item_id are required in payload")

    try:
        order = Order.objects.get(pk=int(order_id))
    except Order.DoesNotExist:
        raise ValidationError(f"Order with ID {order_id} not found")

    try:
        menu_item = MenuItem.objects.get(pk=int(menu_item_id))
    except MenuItem.DoesNotExist:
        raise ValidationError(f"MenuItem with ID {menu_item_id} not found")

    item = svc_add_menu_order_item(
        order=order,
        menu_item=menu_item,
        quantity=payload.get("quantity", 1),
        sold_by=user,
        client_id=client_id,
    )

    return True, {
        "order_item_id": item.id,
        "order_id": item.order_id,
        "line_total": str(item.line_total),
    }


def handle_submit_order(
    user: Employee, payload: Dict[str, Any], client_id: str
) -> Tuple[bool, Dict[str, Any]]:
    receipt_id = payload.get("receipt_id")
    if not receipt_id:
        raise ValidationError("receipt_id is required in payload")

    try:
        receipt = Receipt.objects.get(pk=int(receipt_id))
    except Receipt.DoesNotExist:
        raise ValidationError(f"Receipt with ID {receipt_id} not found")

    updated_receipt = svc_submit_order(
        receipt=receipt,
        performed_by=user,
        emit_stock=payload.get("emit_stock", True),
    )

    return True, {
        "receipt_id": updated_receipt.id,
        "status": updated_receipt.status,
        "total": str(updated_receipt.total),
    }


def handle_accept_payment(
    user: Employee, payload: Dict[str, Any], client_id: str
) -> Tuple[bool, Dict[str, Any]]:
    existing = Payment.objects.filter(client_id=client_id).first()
    if existing:
        return False, {
            "payment_id": existing.id,
            "receipt_id": existing.receipt_id,
            "amount": str(existing.amount),
        }

    receipt_id = payload.get("receipt_id")
    amount = payload.get("amount")
    method = payload.get("method")
    if not receipt_id or amount is None or not method:
        raise ValidationError("receipt_id, amount, and method are required in payload")

    payment = svc_accept_payment(
        receipt_id=int(receipt_id),
        amount=amount,
        method=method,
        received_by=user,
        client_id=client_id,
    )

    return True, {
        "payment_id": payment.id,
        "receipt_id": payment.receipt_id,
        "amount": str(payment.amount),
    }


def handle_create_expense(
    user: Employee, payload: Dict[str, Any], client_id: str
) -> Tuple[bool, Dict[str, Any]]:
    item_name = payload.get("item_name")
    unit_price = payload.get("unit_price")
    quantity = payload.get("quantity")
    if not item_name or unit_price is None or quantity is None:
        raise ValidationError("item_name, unit_price, and quantity are required in payload")

    result = svc_create_expense_item(
        supplier_id=payload.get("supplier_id"),
        supplier_name=payload.get("supplier_name"),
        product_id=payload.get("product_id"),
        item_name=item_name,
        unit_price=unit_price,
        quantity=quantity,
        client_id=client_id,
    )

    expense = result["expense"]
    created = result["created"]

    return created, {
        "expense_id": expense.id,
        "item_name": expense.item_name,
        "total_price": str(expense.total_price),
    }


def handle_add_stock(
    user: Employee, payload: Dict[str, Any], client_id: str
) -> Tuple[bool, Dict[str, Any]]:
    product_id = payload.get("product_id")
    quantity = payload.get("quantity")
    reason = payload.get("reason")
    if not product_id or quantity is None or not reason:
        raise ValidationError("product_id, quantity, and reason are required in payload")

    try:
        product = Product.objects.get(pk=int(product_id))
    except Product.DoesNotExist:
        raise ValidationError(f"Product with ID {product_id} not found")

    movement, created = svc_add_stock(
        product=product,
        quantity=float(quantity),
        reason=reason,
        performed_by=user,
        expense_item_id=payload.get("expense_item_id"),
        funded_by_business=payload.get("funded_by_business", True),
        group_id=payload.get("group_id"),
        notes=payload.get("notes"),
        client_id=client_id,
    )

    return created, {
        "movement_id": movement.id,
        "movement_type": movement.movement_type,
        "quantity": float(movement.quantity),
    }


def handle_remove_stock(
    user: Employee, payload: Dict[str, Any], client_id: str
) -> Tuple[bool, Dict[str, Any]]:
    product_id = payload.get("product_id")
    quantity = payload.get("quantity")
    reason = payload.get("reason")
    if not product_id or quantity is None or not reason:
        raise ValidationError("product_id, quantity, and reason are required in payload")

    try:
        product = Product.objects.get(pk=int(product_id))
    except Product.DoesNotExist:
        raise ValidationError(f"Product with ID {product_id} not found")

    movement, created = svc_remove_stock(
        product=product,
        quantity=float(quantity),
        reason=reason,
        performed_by=user,
        group_id=payload.get("group_id"),
        notes=payload.get("notes"),
        client_id=client_id,
    )

    return created, {
        "movement_id": movement.id,
        "movement_type": movement.movement_type,
        "quantity": float(movement.quantity),
    }
