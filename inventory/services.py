# inventory/services.py

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum, Q, DecimalField
from django.db.models.functions import Coalesce
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    Product,
    ProductPackaging,
    StockMovement,
    StockReconciliation,
)


# ======================================================
# UNIT / PACKAGING CONVERSION
# ======================================================
#
# Product.unit is the canonical BASE unit. Every StockMovement
# quantity is stored in base units. Callers that collect a
# quantity in a packaging (e.g. "2 bales") pass the packaging
# label; to_base_units() converts to base units before the
# movement is created.

def resolve_packaging(
    product: Product,
    packaging_label: str | None,
) -> ProductPackaging | None:
    """
    Returns the ProductPackaging matching the label for this
    product, or None when the label is empty or equals the
    product's base unit (factor 1).
    """
    label = (packaging_label or "").strip()
    if not label:
        return None

    base_unit = (product.unit or "").strip()
    if base_unit and label.lower() == base_unit.lower():
        return None

    try:
        return product.packagings.get(label__iexact=label)
    except ProductPackaging.DoesNotExist:
        raise ValidationError(
            f"Packaging '{label}' not found for product '{product.name}'"
        )


def to_base_units(
    product: Product,
    quantity,
    packaging_label: str | None = None,
) -> Decimal:
    """
    Convert a quantity expressed in a packaging into base units
    (Product.unit). Returns a Decimal quantized to 3 places.
    """
    qty = Decimal(str(quantity))
    packaging = resolve_packaging(product, packaging_label)
    if packaging is None:
        return qty.quantize(Decimal("0.001"))
    return (qty * packaging.quantity_in_base).quantize(Decimal("0.001"))


# ======================================================
# PACKAGING MANAGEMENT
# ======================================================

def create_product_packaging(
    *,
    product: Product,
    label: str,
    quantity_in_base,
    is_purchase_unit: bool = False,
    is_sale_unit: bool = False,
    client_id: str | None = None,
) -> ProductPackaging:
    label = (label or "").strip()
    if not label:
        raise ValidationError("Packaging label is required")

    factor = Decimal(str(quantity_in_base))
    if factor <= 0:
        raise ValidationError("quantity_in_base must be greater than zero")

    base_unit = (product.unit or "").strip()
    if base_unit and label.lower() == base_unit.lower():
        raise ValidationError(
            f"'{label}' is the product's base unit; no packaging needed"
        )

    packaging, _ = ProductPackaging.objects.update_or_create(
        product=product,
        label__iexact=label,
        defaults={
            "label": label,
            "quantity_in_base": factor,
            "is_purchase_unit": is_purchase_unit,
            "is_sale_unit": is_sale_unit,
            "client_id": client_id,
        },
    )
    return packaging


def delete_product_packaging(*, packaging_id: int) -> bool:
    try:
        packaging = ProductPackaging.objects.get(pk=packaging_id)
    except ProductPackaging.DoesNotExist:
        raise ValidationError("Packaging not found")
    packaging.delete()
    return True


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
    product:            Product,
    quantity:           float,
    reason:             str,
    performed_by,
    expense_item_id:    int | None = None,
    funded_by_business: bool = True,
    group_id:           str | None = None,
    notes:              str | None = None,
    client_id:          str | None = None,
    packaging:          str | None = None,
) -> tuple[StockMovement, bool]:

    if client_id:
        existing = StockMovement.objects.filter(client_id=client_id).first()
        if existing:
            return existing, False

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

    base_quantity = to_base_units(product, quantity, packaging)

    movement = StockMovement.objects.create(
        product=product,
        quantity=base_quantity,
        movement_type=StockMovement.IN,
        reason=reason,
        expense_item=expense_item,
        funded_by_business=funded_by_business,
        performed_by=performed_by,
        group_id=group_id,
        notes=notes,
        client_id=client_id,
    )
    return movement, True


# ======================================================
# STOCK OUT
# ======================================================

@transaction.atomic
def remove_stock(
    *,
    product:      Product,
    quantity:     float,
    reason:       str,
    performed_by,
    group_id:     str | None = None,
    notes:        str | None = None,
    client_id:    str | None = None,
    packaging:    str | None = None,
) -> tuple[StockMovement, bool]:

    if client_id:
        existing = StockMovement.objects.filter(client_id=client_id).first()
        if existing:
            return existing, False

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

    base_quantity = to_base_units(product, quantity, packaging)

    available_stock = product.current_stock
    if available_stock < base_quantity:
        raise ValidationError(
            f"Insufficient stock. Available: {available_stock}"
        )

    movement = StockMovement.objects.create(
        product=product,
        quantity=base_quantity,
        movement_type=StockMovement.OUT,
        reason=reason,
        performed_by=performed_by,
        group_id=group_id,
        notes=notes,
        client_id=client_id,
    )
    return movement, True


# ======================================================
# ADD STOCK FROM EXPENSE — ATOMIC
# ======================================================

@transaction.atomic
def add_stock_from_expense(
    *,
    product_id:      int,
    quantity:        float,
    expense_item_id: int,
    performed_by,
    client_id: str | None = None,
    packaging: str | None = None,
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

    if client_id:
        existing = StockMovement.objects.filter(client_id=client_id).first()
        if existing:
            return existing
    return StockMovement.objects.create(
        product=product,
        quantity=to_base_units(product, quantity, packaging),
        movement_type=StockMovement.IN,
        reason=StockMovement.PURCHASE,
        expense_item=expense_item,
        funded_by_business=True,
        performed_by=performed_by,
        client_id=client_id,
        notes=f"Stock added from expense #{expense_item_id}",
    )


# ======================================================
# CREATE PRODUCT STANDALONE (no stock)
# category is now a Category instance, not a string
# ======================================================

def create_product(
    *,
    name:                str,
    unit:                str,
    category=None,
    auto_deduct_on_sale: bool = False,
) -> tuple:

    name = (name or "").strip()
    if not name:
        raise ValidationError("Product name is required")

    return Product.objects.get_or_create(
        name__iexact=name,
        defaults={
            "name":                name,
            "unit":                unit,
            "category":            category,
            "auto_deduct_on_sale": auto_deduct_on_sale,
        },
    )


# ======================================================
# CREATE PRODUCT WITH INITIAL STOCK — ATOMIC
# category is now a Category instance, not a string
# ======================================================

@transaction.atomic
def create_product_with_stock(
    *,
    name:                str,
    unit:                str,
    category=None,
    quantity:            float,
    expense_item_id:     int,
    performed_by,
    auto_deduct_on_sale: bool = False,
    packaging:           str | None = None,
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
            "name":                name,
            "unit":                unit,
            "category":            category,
            "auto_deduct_on_sale": auto_deduct_on_sale,
        },
    )

    movement = StockMovement.objects.create(
        product=product,
        quantity=to_base_units(product, quantity, packaging),
        movement_type=StockMovement.IN,
        reason=StockMovement.PURCHASE,
        expense_item=expense_item,
        funded_by_business=True,
        performed_by=performed_by,
        notes=f"Initial stock from expense #{expense_item_id}",
    )

    return {"product": product, "movement": movement, "created": created}


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

    reconciliation.status      = StockReconciliation.APPROVED
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

    reconciliation.status      = StockReconciliation.REJECTED
    reconciliation.approved_by = approved_by
    reconciliation.approved_at = timezone.now()
    reconciliation.notes       = notes
    reconciliation.save(update_fields=[
        "status", "approved_by", "approved_at", "notes",
    ])

    return reconciliation


# ======================================================
# SUBMIT STOCK RECONCILIATION (BULK)
# ======================================================

@transaction.atomic
def submit_reconciliation(
    *,
    counts:     list[dict],
    counted_by,
) -> list[StockReconciliation]:

    _validate_user(counted_by, "counted_by")

    if not counts:
        raise ValidationError("No counts provided")

    product_ids  = [c["product_id"] for c in counts]
    products_map = {
        p.id: p
        for p in Product.objects.filter(pk__in=product_ids)
    }

    # Batch stock levels — product.current_stock runs an aggregate
    # query per product (N+1). One grouped query instead.
    stock_rows = (
        StockMovement.objects
        .filter(product_id__in=product_ids)
        .values("product_id")
        .annotate(
            total_in=Coalesce(
                Sum("quantity", filter=Q(movement_type=StockMovement.IN)),
                Decimal("0"), output_field=DecimalField(),
            ),
            total_out=Coalesce(
                Sum("quantity", filter=Q(movement_type=StockMovement.OUT)),
                Decimal("0"), output_field=DecimalField(),
            ),
        )
    )
    stock_map = {
        row["product_id"]: float(row["total_in"] - row["total_out"])
        for row in stock_rows
    }

    reconciliations = []
    for entry in counts:
        pid         = entry["product_id"]
        counted_qty = entry["counted_quantity"]

        if counted_qty < 0:
            raise ValidationError(
                f"Counted quantity cannot be negative for product {pid}"
            )

        product = products_map.get(pid)
        if not product:
            raise ValidationError(f"Product with ID {pid} not found")

        system_qty = stock_map.get(pid, 0.0)
        difference = counted_qty - system_qty

        reconciliations.append(
            StockReconciliation(
                product=product,
                system_quantity=system_qty,
                counted_quantity=counted_qty,
                difference=difference,
                status=StockReconciliation.PENDING,
                counted_by=counted_by,
            )
        )

    return StockReconciliation.objects.bulk_create(reconciliations)
