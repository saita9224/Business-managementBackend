# expenses/services.py
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404

from .models import Supplier, ExpenseItem, ExpensePayment
from inventory.models import Product


def create_supplier(name: str) -> Supplier:
    supplier = Supplier(name=name)
    supplier.full_clean()
    supplier.save()
    return supplier


def update_supplier(supplier_id: int, name: str) -> Supplier:
    supplier = get_object_or_404(Supplier, id=supplier_id)
    supplier.name = name
    supplier.full_clean()
    supplier.save()
    return supplier


def delete_supplier(supplier_id: int) -> bool:
    supplier = get_object_or_404(Supplier, id=supplier_id)
    supplier.delete()
    return True


def create_expense_item(
    supplier_id: int | None,
    product_id: int | None,
    item_name: str,
    unit_price: Decimal | float | str,
    quantity: float,
) -> ExpenseItem:

    supplier = Supplier.objects.filter(id=supplier_id).first() if supplier_id else None
    product = Product.objects.filter(id=product_id).first() if product_id else None

    expense = ExpenseItem(
        supplier=supplier,
        product=product,
        item_name=item_name,
        quantity=quantity,
        unit_price=Decimal(str(unit_price)),
    )

    expense.full_clean()
    expense.save()
    return expense


@transaction.atomic
def record_payment(expense_id: int, amount: Decimal | float | str) -> dict:
    """
    Safely records a payment against an expense.
    Uses SELECT ... FOR UPDATE to lock the expense row in the transaction,
    preventing concurrent overpayments.
    """
    amount = Decimal(str(amount))

    if amount <= 0:
        raise ValidationError("Payment amount must be greater than zero.")

    # Lock the expense row for update to prevent race conditions
    try:
        expense = ExpenseItem.objects.select_for_update().get(pk=expense_id)
    except ExpenseItem.DoesNotExist:
        raise ValidationError("Expense not found")

    # Re-check balance while row is locked
    if amount > expense.balance:
        raise ValidationError("Payment exceeds remaining balance.")

    payment = ExpensePayment(expense=expense, amount=amount)
    payment.full_clean()
    payment.save()

    return {"expense": expense, "payment": payment}


def list_expenses_by_supplier(supplier_id: int):
    return ExpenseItem.objects.filter(supplier_id=supplier_id).order_by("-created_at")


def list_expenses_by_item_name(item_name: str):
    return ExpenseItem.objects.filter(item_name__icontains=item_name).order_by("-created_at")


def list_expenses_by_product(product_id: int):
    return ExpenseItem.objects.filter(product_id=product_id).order_by("-created_at")


def get_expense_details(expense_id: int) -> dict:
    expense = get_object_or_404(ExpenseItem, id=expense_id)
    payments = ExpensePayment.objects.filter(expense=expense).order_by("paid_at")
    remaining = expense.balance

    return {
        "expense": expense,
        "payments": list(payments),
        "remaining_balance": remaining,
    }
