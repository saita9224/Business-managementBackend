# expenses/services.py

from django.db import transaction
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from decimal import Decimal
import uuid

from .models import ExpenseItem, ExpensePayment, Supplier


# ============================================================
# SUPPLIER SERVICES
# ============================================================

def create_supplier(name: str) -> Supplier:
    name = name.strip()
    if Supplier.objects.filter(name__iexact=name).exists():
        raise ValidationError("Supplier already exists")
    return Supplier.objects.create(name=name)


def update_supplier(supplier_id: int, name: str) -> Supplier:
    supplier = Supplier.objects.get(id=supplier_id)
    supplier.name = name.strip()
    supplier.save()
    return supplier


def delete_supplier(supplier_id: int) -> bool:
    supplier = Supplier.objects.get(id=supplier_id)
    if supplier.expenses.exists():
        raise ValidationError("Cannot delete supplier with existing expenses.")
    supplier.delete()
    return True


def list_suppliers():
    """
    Return a queryset (or list) of suppliers.
    This satisfies imports from queries.py and provides a simple listing endpoint.
    """
    return Supplier.objects.all()


# ============================================================
# EXPENSE ITEM SERVICES
# ============================================================

def create_expense_item(
    supplier_id: int | None,
    item_name: str,
    unit_price: float,
    quantity: float,
    product_id: int | None = None
) -> ExpenseItem:
    """
    Create an ExpenseItem. total_price computed on model.save().
    """
    if quantity <= 0:
        raise ValidationError("Quantity must be greater than zero.")
    if unit_price <= 0:
        raise ValidationError("Unit price must be greater than zero.")

    # Create the DB record; model.save() will compute total_price and validate
    item = ExpenseItem.objects.create(
        supplier_id=supplier_id,
        product_id=product_id,
        item_name=item_name.strip(),
        unit_price=Decimal(str(unit_price)),
        quantity=quantity,
        # total_price will be set by model.clean/save
    )

    return item


def update_expense_item(expense_id: int, **fields) -> ExpenseItem:
    """
    Update an expense item and recalculate totals if needed.
    Allowed fields: item_name, unit_price, quantity, product_id, supplier_id
    """
    expense = ExpenseItem.objects.get(id=expense_id)

    allowed = {"item_name", "unit_price", "quantity", "product_id", "supplier_id"}

    for key, value in fields.items():
        if key in allowed:
            setattr(expense, key, value)

    # model.save() will recalc totals and validate
    expense.save()
    return expense


def delete_expense_item(expense_id: int) -> bool:
    expense = ExpenseItem.objects.get(id=expense_id)
    if expense.payments.exists():
        raise ValidationError("Cannot delete an expense that already has payments.")
    expense.delete()
    return True


# ============================================================
# PAYMENT SERVICES
# ============================================================

@transaction.atomic
def record_payment(expense_id: int, amount: float):
    """
    Records a payment toward an expense and returns
    {"payment": ExpensePayment, "remaining_balance": Decimal}
    """
    if amount <= 0:
        raise ValidationError("Payment must be greater than zero.")

    # lock row to avoid race conditions
    expense = ExpenseItem.objects.select_for_update().get(id=expense_id)

    remaining = expense.balance
    if Decimal(str(amount)) > remaining:
        raise ValidationError(f"Payment exceeds remaining balance. Remaining: {remaining}")

    payment = ExpensePayment.objects.create(
        expense=expense,
        amount=Decimal(str(amount))
    )

    # No need to update expense (amount_paid is derived)
    remaining_after = expense.balance

    return {
        "payment": payment,
        "remaining_balance": remaining_after
    }


def get_expense_details(expense_id: int):
    expense = ExpenseItem.objects.get(id=expense_id)
    payments = expense.payments.order_by("paid_at")
    return {
        "expense": expense,
        "payments": payments,
        "remaining_balance": expense.balance
    }


# ============================================================
# LISTING / FILTERING SERVICES
# ============================================================

def list_expenses_by_supplier(supplier_id: int):
    return ExpenseItem.objects.filter(supplier_id=supplier_id).order_by("-created_at")


def list_expenses_by_item_name(name: str):
    return ExpenseItem.objects.filter(item_name__icontains=name).order_by("-created_at")


def list_expenses_by_product(product_id: int):
    return ExpenseItem.objects.filter(product_id=product_id).order_by("-created_at")
