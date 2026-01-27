from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    Product,
    StockMovement,
    StockReconciliation,
)

# =========STOCK IN======

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
    """

    if quantity <= 0:
        raise ValidationError("Quantity must be greater than zero")

    if performed_by is None:
        raise ValidationError("performed_by user is required")

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
        group_id=group_id,
        notes=notes,
        performed_by=performed_by,
    )

# =========STOCK OUT======

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


# =========APPROVE RECONCILIATION (CREATES ADJUSTMENT)======

@transaction.atomic
def approve_reconciliation(
    *,
    reconciliation: StockReconciliation,
    approved_by,
) -> StockMovement | None:
    """
    Approves a stock reconciliation and creates an ADJUSTMENT movement.
    """

    if reconciliation.status != StockReconciliation.PENDING:
        raise ValidationError("Only pending reconciliations can be approved")

    if approved_by is None:
        raise ValidationError("approved_by user is required")

    reconciliation.status = StockReconciliation.APPROVED
    reconciliation.approved_by = approved_by
    reconciliation.approved_at = timezone.now()
    reconciliation.save(update_fields=[
        "status",
        "approved_by",
        "approved_at",
    ])

    if reconciliation.difference == 0:
        return None  # No adjustment needed

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


# ==========REJECT RECONCILIATION======

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

    if rejected_by is None:
        raise ValidationError("rejected_by user is required")

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

