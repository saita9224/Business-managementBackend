# inventory/services.py

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    Product,
    StockMovement,
    StockReconciliation,
)


# ======================================================
# INTERNAL HELPERS
# ======================================================

def _validate_quantity(quantity: float):
    if quantity is None or quantity <= 0:
        raise ValidationError("Quantity must be greater than zero")


def _validate_user(user, field_name: str):
    if user is None:
        raise ValidationError(f"{field_name} user is required")


def _validate_reason(reason: str):
    valid_reasons = dict(StockMovement.REASONS)
    if reason not in valid_reasons:
        raise ValidationError(f"Invalid stock reason: {reason}")


# ======================================================
# STOCK IN
# ======================================================

@transaction.atomic
def add_stock(
    *,
    product: Product,
    quantity: float,
    reason: str,
    performed_by,
    expense_item_id: int | None = None,
    funded_by_business: bool = True,
    group_id: str | None = None,
    notes: str | None = None,
) -> StockMovement:

    _validate_quantity(quantity)
    _validate_user(performed_by, "performed_by")
    _validate_reason(reason)

    if reason not in {
        StockMovement.PURCHASE,
        StockMovement.RETURN,
        StockMovement.ADJUSTMENT,
    }:
        raise ValidationError(f"Reason '{reason}' is not valid for stock IN")

    if (
        funded_by_business
        and reason == StockMovement.PURCHASE
        and expense_item_id is None
    ):
        raise ValidationError(
            "Business-funded purchases must be linked to an expense item"
        )

    expense_item = None
    if expense_item_id is not None:
        from expenses.models import ExpenseItem
        try:
            expense_item = ExpenseItem.objects.get(pk=expense_item_id)
        except ExpenseItem.DoesNotExist:
            raise ValidationError(
                f"Expense item with ID {expense_item_id} does not exist"
            )

    return StockMovement.objects.create(
        product=product,
        quantity=quantity,
        movement_type=StockMovement.IN,
        reason=reason,
        expense_item=expense_item,
        funded_by_business=funded_by_business,
        performed_by=performed_by,
        group_id=group_id,
        notes=notes,
    )


# ======================================================
# STOCK OUT
# ======================================================

@transaction.atomic
def remove_stock(
    *,
    product: Product,
    quantity: float,
    reason: str,
    performed_by,
    group_id: str | None = None,
    notes: str | None = None,
) -> StockMovement:

    _validate_quantity(quantity)
    _validate_user(performed_by, "performed_by")
    _validate_reason(reason)

    if reason not in {
        StockMovement.SALE,
        StockMovement.COOKING,
        StockMovement.DAMAGED,
        StockMovement.LOST,
        StockMovement.ADJUSTMENT,
    }:
        raise ValidationError(f"Reason '{reason}' is not valid for stock OUT")

    available_stock = product.current_stock
    if available_stock < quantity:
        raise ValidationError(
            f"Insufficient stock. Available: {available_stock}"
        )

    return StockMovement.objects.create(
        product=product,
        quantity=quantity,
        movement_type=StockMovement.OUT,
        reason=reason,
        performed_by=performed_by,
        group_id=group_id,
        notes=notes,
    )


# ======================================================
# ADD STOCK FROM EXPENSE — ATOMIC (matched product flow)
# Links an existing expense to an existing product.
# Stock movement and expense link written in one transaction.
# If anything fails, nothing is saved.
# ======================================================

@transaction.atomic
def add_stock_from_expense(
    *,
    product_id: int,
    quantity: float,
    expense_item_id: int,
    performed_by,
) -> StockMovement:

    from expenses.models import ExpenseItem

    _validate_quantity(quantity)
    _validate_user(performed_by, "performed_by")

    try:
        product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist:
        raise ValidationError(f"Product with ID {product_id} does not exist")

    try:
        expense_item = ExpenseItem.objects.get(pk=expense_item_id)
    except ExpenseItem.DoesNotExist:
        raise ValidationError(
            f"Expense item with ID {expense_item_id} does not exist"
        )

    return StockMovement.objects.create(
        product=product,
        quantity=quantity,
        movement_type=StockMovement.IN,
        reason=StockMovement.PURCHASE,
        expense_item=expense_item,
        funded_by_business=True,
        performed_by=performed_by,
        notes=f"Stock added from expense #{expense_item_id}",
    )


# ======================================================
# CREATE PRODUCT WITH INITIAL STOCK — ATOMIC (new product flow)
# Creates product + stock movement in one transaction.
# If either step fails everything rolls back —
# no orphaned products, no unlinked stock movements.
# ======================================================

@transaction.atomic
def create_product_with_stock(
    *,
    name: str,
    unit: str,
    category: str | None,
    quantity: float,
    expense_item_id: int,
    performed_by,
) -> dict:

    from expenses.models import ExpenseItem

    _validate_quantity(quantity)
    _validate_user(performed_by, "performed_by")

    name = (name or "").strip()
    if not name:
        raise ValidationError("Product name is required")

    try:
        expense_item = ExpenseItem.objects.get(pk=expense_item_id)
    except ExpenseItem.DoesNotExist:
        raise ValidationError(
            f"Expense item with ID {expense_item_id} does not exist"
        )

    product, created = Product.objects.get_or_create(
        name__iexact=name,
        defaults={
            "name": name,
            "unit": unit,
            "category": category,
        },
    )

    movement = StockMovement.objects.create(
        product=product,
        quantity=quantity,
        movement_type=StockMovement.IN,
        reason=StockMovement.PURCHASE,
        expense_item=expense_item,
        funded_by_business=True,
        performed_by=performed_by,
        notes=f"Initial stock from expense #{expense_item_id}",
    )

    return {
        "product": product,
        "movement": movement,
        "created": created,
    }


# ======================================================
# APPROVE RECONCILIATION
# ======================================================

@transaction.atomic
def approve_reconciliation(
    *,
    reconciliation: StockReconciliation,
    approved_by,
) -> StockMovement | None:

    if reconciliation.status != StockReconciliation.PENDING:
        raise ValidationError("Only pending reconciliations can be approved")

    _validate_user(approved_by, "approved_by")

    reconciliation.status = StockReconciliation.APPROVED
    reconciliation.approved_by = approved_by
    reconciliation.approved_at = timezone.now()
    reconciliation.save(update_fields=["status", "approved_by", "approved_at"])

    if reconciliation.difference == 0:
        return None

    movement_type = (
        StockMovement.IN
        if reconciliation.difference > 0
        else StockMovement.OUT
    )

    return StockMovement.objects.create(
        product=reconciliation.product,
        quantity=abs(reconciliation.difference),
        movement_type=movement_type,
        reason=StockMovement.ADJUSTMENT,
        funded_by_business=False,
        performed_by=approved_by,
        group_id=f"recon-{reconciliation.id}",
        notes="Stock reconciliation adjustment",
    )


# ======================================================
# REJECT RECONCILIATION
# ======================================================

@transaction.atomic
def reject_reconciliation(
    *,
    reconciliation: StockReconciliation,
    approved_by,
    notes: str | None = None,
) -> StockReconciliation:

    if reconciliation.status != StockReconciliation.PENDING:
        raise ValidationError("Only pending reconciliations can be rejected")

    _validate_user(approved_by, "approved_by")

    reconciliation.status = StockReconciliation.REJECTED
    reconciliation.approved_by = approved_by
    reconciliation.approved_at = timezone.now()
    reconciliation.notes = notes
    reconciliation.save(update_fields=[
        "status", "approved_by", "approved_at", "notes",
    ])

    return reconciliation