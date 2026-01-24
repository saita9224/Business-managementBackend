from django.db import transaction
from django.core.exceptions import ValidationError

from .models import Product, StockMovement


# ───────────────────────────────────────────────
# STOCK IN
# ───────────────────────────────────────────────

@transaction.atomic
def add_stock(
    *,
    product: Product,
    quantity: float,
    reason: str,
    performed_by,
    expense_item=None,
    funded_by_business: bool = True,
    group_id: str | None = None,
    notes: str | None = None
) -> StockMovement:
    """
    Adds stock to inventory.
    """

    if quantity <= 0:
        raise ValidationError("Quantity must be greater than zero")

    if performed_by is None:
        raise ValidationError("performed_by user is required")

    if funded_by_business and expense_item is None and reason == StockMovement.PURCHASE:
        raise ValidationError(
            "Business-funded purchases must be linked to an expense item"
        )

    return StockMovement.objects.create(
        product=product,
        quantity=quantity,
        movement_type=StockMovement.IN,
        reason=reason,
        expense_item=expense_item,
        funded_by_business=funded_by_business,
        group_id=group_id,
        notes=notes,
        performed_by=performed_by,
    )


# ───────────────────────────────────────────────
# STOCK OUT
# ───────────────────────────────────────────────

@transaction.atomic
def remove_stock(
    *,
    product: Product,
    quantity: float,
    reason: str,
    performed_by,
    group_id: str | None = None,
    notes: str | None = None
) -> StockMovement:
    """
    Removes stock from inventory.
    Prevents negative stock.
    """

    if quantity <= 0:
        raise ValidationError("Quantity must be greater than zero")

    if performed_by is None:
        raise ValidationError("performed_by user is required")

    if product.current_stock < quantity:
        raise ValidationError(
            f"Insufficient stock. Available: {product.current_stock}"
        )

    return StockMovement.objects.create(
        product=product,
        quantity=quantity,
        movement_type=StockMovement.OUT,
        reason=reason,
        group_id=group_id,
        notes=notes,
        performed_by=performed_by,
    )


# ───────────────────────────────────────────────
# STOCK ADJUSTMENT (ADMIN / AUDIT)
# ───────────────────────────────────────────────

@transaction.atomic
def adjust_stock(
    *,
    product: Product,
    new_quantity: float,
    performed_by,
    notes: str | None = None
):
    """
    Adjusts stock to match a physical count.
    Creates either IN or OUT adjustment.
    """

    if performed_by is None:
        raise ValidationError("performed_by user is required")

    if new_quantity < 0:
        raise ValidationError("Stock cannot be negative")

    current = product.current_stock
    difference = new_quantity - current

    if difference == 0:
        return None

    return StockMovement.objects.create(
        product=product,
        quantity=abs(difference),
        movement_type=(
            StockMovement.IN if difference > 0 else StockMovement.OUT
        ),
        reason=StockMovement.ADJUSTMENT,
        funded_by_business=False,
        notes=notes,
        performed_by=performed_by,
    )
