# expenses/services.py

from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.db.models import Sum

from .models import Supplier, ExpenseItem, ExpensePayment
from .utils import to_decimal
from inventory.models import Product


# --------------------------------------------------
# SUPPLIER SERVICES
# --------------------------------------------------

def create_supplier(name: str) -> Supplier:
    name = (name or "").strip()

    if not name:
        raise ValidationError("Supplier name is required.")

    supplier = Supplier(name=name.title())
    supplier.full_clean()
    supplier.save()

    return supplier


def update_supplier(supplier_id: int, name: str) -> Supplier:
    supplier = get_object_or_404(Supplier, id=supplier_id)

    name = (name or "").strip()

    if not name:
        raise ValidationError("Supplier name is required.")

    supplier.name = name.title()
    supplier.full_clean()
    supplier.save()

    return supplier


def delete_supplier(supplier_id: int) -> bool:
    supplier = get_object_or_404(Supplier, id=supplier_id)
    supplier.delete()
    return True


# --------------------------------------------------
# HELPER RESOLUTION FUNCTIONS
# --------------------------------------------------

def resolve_supplier(
    supplier_id: int | None,
    supplier_name: str | None
) -> Supplier:
    """
    Resolve supplier using ID or name.
    """

    if supplier_id:

        supplier = Supplier.objects.filter(id=supplier_id).first()

        if not supplier:
            raise ValidationError("Supplier with given ID does not exist.")

        return supplier

    if supplier_name:

        cleaned = supplier_name.strip()

        if not cleaned:
            raise ValidationError("Supplier name cannot be empty.")

        cleaned = cleaned.title()

        supplier, _ = Supplier.objects.get_or_create(
            name=cleaned
        )

        return supplier

    raise ValidationError("Supplier is required.")


def resolve_product(product_id: int | None) -> Product | None:
    """
    Resolve product if provided.
    """

    if not product_id:
        return None

    return Product.objects.filter(id=product_id).first()


# --------------------------------------------------
# EXPENSE CREATION
# --------------------------------------------------

@transaction.atomic
def create_expense_item(
    supplier_id: int | None,
    supplier_name: str | None,
    product_id: int | None,
    item_name: str,
    unit_price: Decimal | float | str,
    quantity: Decimal | float | str,
) -> ExpenseItem:
    """
    Create an expense item.

    Payments are recorded separately.
    """

    supplier = resolve_supplier(supplier_id, supplier_name)
    product = resolve_product(product_id)

    unit_price = to_decimal(unit_price, "unit_price")
    quantity = to_decimal(quantity, "quantity")

    cleaned_item = (item_name or "").strip()

    if not cleaned_item:
        raise ValidationError("Item name is required.")

    if quantity <= 0:
        raise ValidationError("Quantity must be greater than zero.")

    if unit_price <= 0:
        raise ValidationError("Unit price must be greater than zero.")

    # Pre-compute total_price so full_clean() does not find it null
    total_price = (quantity * unit_price).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    expense = ExpenseItem(
        supplier=supplier,
        product=product,
        item_name=cleaned_item,
        quantity=quantity,
        unit_price=unit_price,
        total_price=total_price,       # 👈 fix
    )

    expense.full_clean()
    expense.save()

    return expense


# --------------------------------------------------
# PAYMENT RECORDING
# --------------------------------------------------

@transaction.atomic
def record_payment(
    expense_id: int,
    amount: Decimal | float | str
) -> dict:
    """
    Record payment for an expense.
    """

    amount = to_decimal(amount, "amount")

    if amount <= 0:
        raise ValidationError(
            "Payment amount must be greater than zero."
        )

    try:

        expense = (
            ExpenseItem.objects
            .select_for_update()
            .get(pk=expense_id)
        )

    except ExpenseItem.DoesNotExist:

        raise ValidationError("Expense not found.")

    payment = ExpensePayment(
        expense=expense,
        amount=amount,
    )

    payment.full_clean()
    payment.save()

    return {
        "expense": expense,
        "payment": payment,
    }


# --------------------------------------------------
# EXPENSE QUERIES
# --------------------------------------------------

def list_expenses_by_supplier(supplier_id: int):

    return (
        ExpenseItem.objects
        .filter(supplier_id=supplier_id)
        .select_related("supplier", "product")
        .order_by("-created_at")
    )


def list_expenses_by_item_name(item_name: str):

    return (
        ExpenseItem.objects
        .filter(item_name__icontains=item_name)
        .select_related("supplier", "product")
        .order_by("-created_at")
    )


def list_expenses_by_product(product_id: int):

    return (
        ExpenseItem.objects
        .filter(product_id=product_id)
        .select_related("supplier", "product")
        .order_by("-created_at")
    )


# --------------------------------------------------
# EXPENSE DETAILS
# --------------------------------------------------

def get_expense_details(expense_id: int) -> dict:
    """
    Return expense with payments and remaining balance.
    """

    expense = (
        ExpenseItem.objects
        .select_related("supplier", "product")
        .get(id=expense_id)
    )

    payments = list(
        ExpensePayment.objects
        .filter(expense=expense)
        .order_by("paid_at")
    )

    total_paid = (
        ExpensePayment.objects
        .filter(expense=expense)
        .aggregate(total=Sum("amount"))
        .get("total")
        or Decimal("0.00")
    )

    remaining_balance = expense.total_price - total_paid

    return {
        "expense": expense,
        "payments": payments,
        "remaining_balance": remaining_balance,
    }