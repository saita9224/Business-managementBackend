# sync/handlers.py

from typing import Dict, Any, Tuple
from datetime import date
from django.core.exceptions import ValidationError

from employees.models import Employee
from POS.models import Receipt, POSSession, MenuItem, OrderItem, Payment, Order
from POS.services import (
    create_receipt as svc_create_receipt,
    create_order as svc_create_order,
    add_order_item as svc_add_order_item,
    add_menu_order_item as svc_add_menu_order_item,
    submit_order as svc_submit_order,
    accept_payment as svc_accept_payment,
)
from expenses.services import (
    create_expense_item as svc_create_expense_item,
    record_payment as svc_record_payment,
)
from inventory.models import Product
from inventory.services import (
    add_stock as svc_add_stock,
    remove_stock as svc_remove_stock,
)
from hr.services import self_check_in, self_check_out, request_leave
from hr.models import AttendanceRecord, LeaveRequest


def _resolve(model, value):
    """Resolve either a server primary key or an offline client UUID."""
    if value in (None, ""):
        return None
    try:
        return model.objects.get(pk=int(value))
    except (ValueError, TypeError, model.DoesNotExist):
        if any(field.name == "client_id" for field in model._meta.fields):
            return model.objects.filter(client_id=str(value)).first()
        return None


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
    receipt_id = payload.get("receipt_id") or payload.get("receiptId")
    if not receipt_id:
        raise ValidationError("receipt_id is required in payload")

    try:
        receipt = _resolve(Receipt, receipt_id)
        if receipt is None:
            raise Receipt.DoesNotExist
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

    order_id = payload.get("order_id") or payload.get("orderId")
    product_id = payload.get("product_id")
    if not order_id or not product_id:
        raise ValidationError("order_id and product_id are required in payload")

    try:
        order = _resolve(Order, order_id)
        if order is None:
            raise Order.DoesNotExist
    except Order.DoesNotExist:
        raise ValidationError(f"Order with ID {order_id} not found")

    try:
        product = _resolve(Product, product_id)
        if product is None:
            raise Product.DoesNotExist
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

    order_id = payload.get("order_id") or payload.get("orderId")
    menu_item_id = payload.get("menu_item_id")
    if not order_id or not menu_item_id:
        raise ValidationError("order_id and menu_item_id are required in payload")

    try:
        order = _resolve(Order, order_id)
        if order is None:
            raise Order.DoesNotExist
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
    receipt_id = payload.get("receipt_id") or payload.get("receiptId")
    if not receipt_id:
        raise ValidationError("receipt_id is required in payload")

    try:
        receipt = _resolve(Receipt, receipt_id)
        if receipt is None:
            raise Receipt.DoesNotExist
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

    receipt_id = payload.get("receipt_id") or payload.get("receiptId")
    amount = payload.get("amount")
    method = payload.get("method")
    if not receipt_id or amount is None or not method:
        raise ValidationError("receipt_id, amount, and method are required in payload")

    receipt = _resolve(Receipt, receipt_id)
    if not receipt:
        raise ValidationError(f"Receipt {receipt_id} not found")
    payment = svc_accept_payment(
        receipt_id=receipt.id,
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

    amount_paid = payload.get("amount_paid")
    if amount_paid is not None and float(amount_paid) > 0:
        from employees.models import RolePermission
        is_admin = user.roles.filter(name__iexact="Admin").exists()
        can_pay = RolePermission.objects.filter(
            role__in=user.roles.all(), permission__code="expenses.pay"
        ).exists()
        if not (is_admin or can_pay):
            raise ValidationError("Permission denied: expenses.pay")

    result = svc_create_expense_item(
        supplier_id=payload.get("supplier_id"),
        supplier_name=payload.get("supplier_name"),
        product_id=payload.get("product_id"),
        item_name=item_name,
        unit_price=unit_price,
        quantity=quantity,
        client_id=client_id,
        inventory_action=payload.get("inventory_action"),
        inventory_product_id=payload.get("inventory_product_id"),
        product_name=payload.get("product_name"),
        product_unit=payload.get("product_unit"),
        category_id=payload.get("category_id"),
        auto_deduct_on_sale=payload.get("auto_deduct_on_sale", False),
        product_client_id=payload.get("product_client_id"),
        initial_payment=payload.get("amount_paid"),
        performed_by=user,
    )

    expense = result["expense"]
    created = result["created"]

    return created, {
        "expense_id": expense.id,
        "item_name": expense.item_name,
        "total_price": str(expense.total_price),
        "product_id": expense.product_id,
    }
    

def handle_pay_balance(
    user: Employee, payload: Dict[str, Any], client_id: str
) -> Tuple[bool, Dict[str, Any]]:
    expense_id = payload.get("expense_id") or payload.get("expenseId")
    amount = payload.get("amount")
    if not expense_id or amount is None:
        raise ValidationError("expense_id and amount are required in payload")

    from expenses.models import ExpenseItem
    expense = _resolve(ExpenseItem, expense_id)
    if not expense:
        raise ValidationError(f"Expense {expense_id} not found")
    result = svc_record_payment(expense_id=expense.id, amount=amount)
    return True, {
        "expense_id": expense_id,
        "amount_paid": str(result.get("amount_paid", amount)),
        "balance": str(result.get("balance", "0")),
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
        product = _resolve(Product, product_id)
        if product is None:
            raise Product.DoesNotExist
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
        product = _resolve(Product, product_id)
        if product is None:
            raise Product.DoesNotExist
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


def handle_create_category(user, payload, client_id):
    from inventory.models import Category
    category = Category.objects.filter(client_id=client_id).first()
    created = category is None
    if category is None:
        category, _ = Category.objects.get_or_create(
            name__iexact=(payload.get("name") or "").strip(),
            defaults={"name": (payload.get("name") or "").strip(), "client_id": client_id},
        )
        if category.client_id is None:
            category.client_id = client_id
            category.save(update_fields=["client_id"])
    return created, {"category_id": category.id}


def handle_create_product(user, payload, client_id):
    from inventory.models import Category
    category = _resolve(Category, payload.get("category_id"))
    name = (payload.get("name") or "").strip()
    product = Product.objects.filter(client_id=client_id).first()
    if product:
        created = False
    else:
        product = Product.objects.filter(name__iexact=name).first()
        created = product is None
        if product is None:
            product = Product.objects.create(
                name=name, unit=payload.get("unit") or "pcs", category=category,
                auto_deduct_on_sale=payload.get("auto_deduct_on_sale", False),
                client_id=client_id,
            )
        elif product.client_id is None:
            product.client_id = client_id
            product.save(update_fields=["client_id"])
    if created and float(payload.get("quantity") or 0) > 0:
        reason = payload.get("reason") or "ADJUSTMENT"
        if reason == "PURCHASE":
            reason = "ADJUSTMENT"
        svc_add_stock(
            product=product,
            quantity=float(payload["quantity"]),
            reason=reason,
            performed_by=user,
            funded_by_business=False,
            notes=payload.get("notes"),
        )
    return created, {"product_id": product.id}


def handle_create_product_with_stock(user, payload, client_id):
    from expenses.models import ExpenseItem
    from inventory.models import Category
    category = _resolve(Category, payload.get("category_id"))
    expense = _resolve(ExpenseItem, payload.get("expense_item_id"))
    if not expense:
        raise ValidationError("Expense item not found for initial stock")
    product, _ = Product.objects.get_or_create(
        name__iexact=(payload.get("name") or "").strip(),
        defaults={
            "name": (payload.get("name") or "").strip(),
            "unit": payload.get("unit") or "pcs",
            "category": category,
            "auto_deduct_on_sale": payload.get("auto_deduct_on_sale", False),
            "client_id": client_id,
        },
    )
    if product.client_id is None:
        product.client_id = client_id
        product.save(update_fields=["client_id"])
    if product.movements.filter(expense_item=expense, reason="PURCHASE").exists():
        return False, {"product_id": product.id}
    from inventory.models import StockMovement
    StockMovement.objects.create(
        product=product, quantity=payload.get("quantity"), movement_type="IN",
        reason="PURCHASE", expense_item=expense, funded_by_business=True,
        performed_by=user,
    )
    return True, {"product_id": product.id}


def handle_add_stock_from_expense(user, payload, client_id):
    from expenses.models import ExpenseItem
    from inventory.models import StockMovement
    prior = StockMovement.objects.filter(client_id=client_id).first()
    if prior:
        return False, {"movement_id": prior.id}
    product = _resolve(Product, payload.get("product_id"))
    expense = _resolve(ExpenseItem, payload.get("expense_item_id"))
    if not product or not expense:
        raise ValidationError("Product and expense must exist before adding stock")
    movement, created = svc_add_stock(
        product=product, quantity=float(payload.get("quantity") or 0),
        reason="PURCHASE", performed_by=user, expense_item_id=expense.id,
        funded_by_business=True, client_id=client_id,
    )
    return created, {"movement_id": movement.id}


def handle_refund_receipt(user, payload, client_id):
    from POS.services import refund_receipt as svc_refund
    receipt = _resolve(Receipt, payload.get("receipt_id") or payload.get("receiptId"))
    if not receipt:
        raise ValidationError("Receipt not found")
    if receipt.status == Receipt.REFUNDED:
        return False, {"receipt_id": receipt.id, "status": receipt.status}
    updated = svc_refund(
        receipt_id=receipt.id, reason=payload.get("reason") or "",
        refunded_by=user, restock_inventory=bool(payload.get("restock_inventory", False)),
    )
    return True, {"receipt_id": updated.id, "status": updated.status}


def handle_self_check_in(user, payload, client_id):
    record = self_check_in(employee=user, client_id=client_id)
    return True, {"attendance_id": record.id, "date": record.date.isoformat()}


def handle_self_check_out(user, payload, client_id):
    prior = AttendanceRecord.objects.filter(checkout_client_id=client_id).first()
    if prior:
        return False, {"attendance_id": prior.id}
    record = self_check_out(employee=user, client_id=client_id)
    return True, {"attendance_id": record.id}


def handle_request_leave(user, payload, client_id):
    start_date = payload.get("start_date") or payload.get("startDate")
    end_date = payload.get("end_date") or payload.get("endDate")
    leave = request_leave(
        employee=user,
        leave_type=payload.get("leave_type") or payload.get("leaveType"),
        start_date=date.fromisoformat(start_date) if isinstance(start_date, str) else start_date,
        end_date=date.fromisoformat(end_date) if isinstance(end_date, str) else end_date,
        reason=payload.get("reason"),
        client_id=client_id,
    )
    return True, {"leave_request_id": leave.id, "status": leave.status}
