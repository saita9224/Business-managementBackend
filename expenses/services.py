# expenses/services.py

from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404

from .models import Supplier, ExpenseItem, ExpensePayment
from inventory.models import Product


# -------------------------------
# SUPPLIER SERVICES
# -------------------------------

def create_supplier(name: str) -> Supplier:
    name = (name or "").strip()

    if not name:
        raise ValidationError("Supplier name is required.")

    supplier = Supplier(name=name)
    supplier.full_clean()
    supplier.save()
    return supplier


def update_supplier(supplier_id: int, name: str) -> Supplier:
    supplier = get_object_or_404(Supplier, id=supplier_id)

    name = (name or "").strip()
    if not name:
        raise ValidationError("Supplier name is required.")

    supplier.name = name
    supplier.full_clean()
    supplier.save()
    return supplier


def delete_supplier(supplier_id: int) -> bool:
    supplier = get_object_or_404(Supplier, id=supplier_id)
    supplier.delete()
    return True


# -------------------------------
# EXPENSE CREATION (HYBRID DESIGN)
# -------------------------------

@transaction.atomic
def create_expense_item(
    supplier_id: int | None,
    supplier_name: str | None,
    product_id: int | None,
    item_name: str,
    unit_price: Decimal | float | str,
    quantity: Decimal | float | str,
    amount_paid: Decimal | float | str | None = 0,
) -> ExpenseItem:
    """
    Hybrid Supplier Resolution + Optional Initial Payment
    """

    # -------------------------------
    # SUPPLIER RESOLUTION
    # -------------------------------
    supplier = None

    if supplier_id:
        supplier = Supplier.objects.filter(id=supplier_id).first()
        if not supplier:
            raise ValidationError("Supplier with given ID does not exist.")

    elif supplier_name:
        cleaned_name = supplier_name.strip()

        if not cleaned_name:
            raise ValidationError("Supplier name cannot be empty.")

        cleaned_name = cleaned_name.title()
        supplier, _ = Supplier.objects.get_or_create(name=cleaned_name)

    else:
        raise ValidationError("Supplier is required.")

    # -------------------------------
    # PRODUCT RESOLUTION (OPTIONAL)
    # -------------------------------
    product = None
    if product_id:
        product = Product.objects.filter(id=product_id).first()

    # -------------------------------
    # NUMERIC VALIDATION
    # -------------------------------
    try:
        unit_price = Decimal(str(unit_price))
        quantity = Decimal(str(quantity))
        amount_paid = Decimal(str(amount_paid or 0))
    except Exception:
        raise ValidationError("Invalid numeric values.")

    if unit_price <= 0:
        raise ValidationError("Unit price must be greater than zero.")

    if quantity <= 0:
        raise ValidationError("Quantity must be greater than zero.")

    if amount_paid < 0:
        raise ValidationError("Paid amount cannot be negative.")

    total_price = unit_price * quantity

    if amount_paid > total_price:
        raise ValidationError("Paid amount cannot exceed total price.")

    # -------------------------------
    # CREATE EXPENSE
    # -------------------------------
    expense = ExpenseItem(
        supplier=supplier,
        product=product,
        item_name=(item_name or "").strip(),
        quantity=quantity,
        unit_price=unit_price,
        total_price=total_price,
    )

    expense.full_clean()
    expense.save()

    # -------------------------------
    # OPTIONAL INITIAL PAYMENT
    # -------------------------------
    if amount_paid > 0:
        payment = ExpensePayment(
            expense=expense,
            amount=amount_paid
        )
        payment.full_clean()
        payment.save()

    return expense


# -------------------------------
# PAYMENT RECORDING
# -------------------------------

@transaction.atomic
def record_payment(expense_id: int, amount: Decimal | float | str) -> dict:
    amount = Decimal(str(amount))

    if amount <= 0:
        raise ValidationError("Payment amount must be greater than zero.")

    try:
        expense = ExpenseItem.objects.select_for_update().get(pk=expense_id)
    except ExpenseItem.DoesNotExist:
        raise ValidationError("Expense not found.")

    if amount > expense.balance:
        raise ValidationError("Payment exceeds remaining balance.")

    payment = ExpensePayment(expense=expense, amount=amount)
    payment.full_clean()
    payment.save()

    return {"expense": expense, "payment": payment}


# -------------------------------
# QUERIES
# -------------------------------

def list_expenses_by_supplier(supplier_id: int):
    return ExpenseItem.objects.filter(
        supplier_id=supplier_id
    ).order_by("-created_at")


def list_expenses_by_item_name(item_name: str):
    return ExpenseItem.objects.filter(
        item_name__icontains=item_name
    ).order_by("-created_at")


def list_expenses_by_product(product_id: int):
    return ExpenseItem.objects.filter(
        product_id=product_id
    ).order_by("-created_at")


def get_expense_details(expense_id: int) -> dict:
    expense = get_object_or_404(ExpenseItem, id=expense_id)

    payments = ExpensePayment.objects.filter(
        expense=expense
    ).order_by("paid_at")

    return {
        "expense": expense,
        "payments": list(payments),
        "remaining_balance": expense.balance,
    }