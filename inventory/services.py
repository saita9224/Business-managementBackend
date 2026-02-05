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
    expense_item=None,
    funded_by_business: bool = True,
    group_id: str | None = None,
    notes: str | None = None,
) -> StockMovement:
    """
    Adds stock to inventory (IN movement).

    Used for:
    - Purchases
    - Returns
    - Positive adjustments
    """

    _validate_quantity(quantity)
    _validate_user(performed_by, "performed_by")
    _validate_reason(reason)

    # ---- Business rules ----
    if reason not in {
        StockMovement.PURCHASE,
        StockMovement.RETURN,
        StockMovement.ADJUSTMENT,
    }:
        raise ValidationError(
            f"Reason '{reason}' is not valid for stock IN"
        )

    if (
        funded_by_business
        and reason == StockMovement.PURCHASE
        and expense_item is None
    ):
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
    """
    Removes stock from inventory (OUT movement).

    Used for:
    - POS sales
    - Cooking / production
    - Damage
    - Loss
    - Negative adjustments
    """

    _validate_quantity(quantity)
    _validate_user(performed_by, "performed_by")
    _validate_reason(reason)

    # ---- Business rules ----
    if reason not in {
        StockMovement.SALE,
        StockMovement.COOKING,
        StockMovement.DAMAGED,
        StockMovement.LOST,
        StockMovement.ADJUSTMENT,
    }:
        raise ValidationError(
            f"Reason '{reason}' is not valid for stock OUT"
        )

    # Enforce inventory reality
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
# APPROVE RECONCILIATION
# ======================================================
@transaction.atomic
def approve_reconciliation(
    *,
    reconciliation: StockReconciliation,
    approved_by,
) -> StockMovement | None:
    """
    Approves a stock reconciliation.

    Creates an ADJUSTMENT StockMovement if there is a difference.
    """

    if reconciliation.status != StockReconciliation.PENDING:
        raise ValidationError("Only pending reconciliations can be approved")

    _validate_user(approved_by, "approved_by")

    reconciliation.status = StockReconciliation.APPROVED
    reconciliation.approved_by = approved_by
    reconciliation.approved_at = timezone.now()
    reconciliation.save(update_fields=[
        "status",
        "approved_by",
        "approved_at",
    ])

    if reconciliation.difference == 0:
        return None  # No stock impact

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
    rejected_by,
    notes: str | None = None,
) -> StockReconciliation:
    """
    Rejects a stock reconciliation.

    No inventory impact.
    """

    if reconciliation.status != StockReconciliation.PENDING:
        raise ValidationError("Only pending reconciliations can be rejected")

    _validate_user(rejected_by, "rejected_by")

    reconciliation.status = StockReconciliation.REJECTED
    reconciliation.approved_by = rejected_by
    reconciliation.approved_at = timezone.now()
    reconciliation.notes = notes
    reconciliation.save(update_fields=[
        "status",
        "approved_by",
        "approved_at",
        "notes",
    ])

    return reconciliation
