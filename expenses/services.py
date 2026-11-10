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
    supplier_name: str | None,
) -> Supplier | None:
    if supplier_id:
        supplier = Supplier.objects.filter(id=supplier_id).first()
        if not supplier:
            raise ValidationError("Supplier with given ID does not exist.")
        return supplier

    if supplier_name:
        cleaned = supplier_name.strip()
        if not cleaned:
            raise ValidationError("Supplier name cannot be empty.")
        supplier, _ = Supplier.objects.get_or_create(name=cleaned.title())
        return supplier

    return None


def resolve_product(product_id: int | None) -> Product | None:
    if not product_id:
        return None
    try:
        return Product.objects.filter(id=int(product_id)).first()
    except (TypeError, ValueError):
        return Product.objects.filter(client_id=str(product_id)).first()


# --------------------------------------------------
# MATCH PRODUCT BY ITEM NAME
# --------------------------------------------------

def match_product_by_name(item_name: str) -> Product | None:
    """
    Case-insensitive lookup of an inventory product by name.
    Returns the product if found, None otherwise.
    Used to prompt the frontend to add stock after an expense is created.
    """
    return Product.objects.filter(
        name__iexact=item_name.strip()
    ).first()


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
    client_id: str | None = None,
    inventory_action: str | None = None,
    inventory_product_id: int | None = None,
    product_name: str | None = None,
    product_unit: str | None = None,
    category_id: int | None = None,
    auto_deduct_on_sale: bool = False,
    product_client_id: str | None = None,
    initial_payment: Decimal | float | str | None = None,
    performed_by=None,
) -> dict:
    """
    Create an expense item.

    Returns a dict with:
    - expense: the ExpenseItem
    - matched_product: an inventory Product if item_name matches one, else None
    - created: bool indicating whether a new record was created or existing duplicate was returned
    """
    if client_id:
        existing = ExpenseItem.objects.filter(client_id=client_id).first()
        if existing:
            return {
                "expense": existing,
                "matched_product": match_product_by_name(existing.item_name),
                "created": False,
            }

    supplier = resolve_supplier(supplier_id, supplier_name)
    from inventory.models import Category, StockMovement

    action = (inventory_action or "NONE").upper()
    product = resolve_product(inventory_product_id or product_id)
    if action == "ADD_EXISTING":
        product = product or match_product_by_name(item_name)
        if not product:
            raise ValidationError("Selected inventory product was not found")
    elif action == "CREATE_PRODUCT":
        cleaned_product_name = (product_name or item_name or "").strip()
        if not cleaned_product_name:
            raise ValidationError("Product name is required")
        category = Category.objects.filter(pk=category_id).first() if category_id else None
        product, _ = Product.objects.get_or_create(
            name__iexact=cleaned_product_name,
            defaults={
                "name": cleaned_product_name,
                "unit": product_unit or "pcs",
                "category": category,
                "auto_deduct_on_sale": auto_deduct_on_sale,
                "client_id": product_client_id,
            },
        )
        if product_client_id and product.client_id is None:
            product.client_id = product_client_id
            product.save(update_fields=["client_id"])
    elif action != "NONE":
        raise ValidationError("inventory_action must be NONE, ADD_EXISTING, or CREATE_PRODUCT")

    unit_price = to_decimal(unit_price, "unit_price")
    quantity = to_decimal(quantity, "quantity")

    cleaned_item = (item_name or "").strip()

    if not cleaned_item:
        raise ValidationError("Item name is required.")
    if quantity <= 0:
        raise ValidationError("Quantity must be greater than zero.")
    if unit_price <= 0:
        raise ValidationError("Unit price must be greater than zero.")

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
        total_price=total_price,
        client_id=client_id,
    )
    expense.full_clean()
    expense.save()

    if initial_payment is not None and to_decimal(initial_payment, "amount_paid") > 0:
        record_payment(expense_id=expense.id, amount=initial_payment)

    # 👇 Check if item_name matches an existing inventory product
    matched_product = match_product_by_name(cleaned_item)
    if action in {"ADD_EXISTING", "CREATE_PRODUCT"}:
        StockMovement.objects.create(
            product=product,
            quantity=quantity,
            movement_type=StockMovement.IN,
            reason=StockMovement.PURCHASE,
            expense_item=expense,
            funded_by_business=True,
            performed_by=performed_by,
        )
        matched_product = product

    return {
        "expense": expense,
        "matched_product": matched_product,
        "created": True,
    }


# --------------------------------------------------
# PAYMENT RECORDING
# --------------------------------------------------

@transaction.atomic
def record_payment(
    expense_id: int,
    amount: Decimal | float | str,
) -> dict:
    amount = to_decimal(amount, "amount")

    if amount <= 0:
        raise ValidationError("Payment amount must be greater than zero.")

    try:
        expense = (
            ExpenseItem.objects
            .select_for_update()
            .get(pk=expense_id)
        )
    except ExpenseItem.DoesNotExist:
        raise ValidationError("Expense not found.")

    payment = ExpensePayment(expense=expense, amount=amount)
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
