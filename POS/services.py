# POS/services.py

from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from employees.models import Employee
from inventory.models import Product, StockMovement
from inventory.services import remove_stock
from inventory.models import Product as InventoryProduct

from .models import (
    POSSession,
    Receipt,
    Order,
    OrderItem,
    Payment,
    CreditAccount,
    POSStockMovement,
    MenuItem,
)

# ── Shared precision constant ─────────────────────────────
TWO = Decimal("0.01")


# ── Internal helper: sync MenuItem.price → PriceListItem ──
# Called whenever an inventory-linked MenuItem is created or
# its price is updated. Keeps PriceListItem in sync so that
# listed_price on OrderItem always reflects the official price.

def _sync_price_list_item(menu_item: MenuItem) -> None:
    """
    Creates or updates the PriceListItem for the product linked to
    this MenuItem in the default PriceList.
    No-op if the MenuItem has no product link.
    """
    if menu_item.product_id is None:
        return

    from .models import PriceList, PriceListItem

    price_list = PriceList.objects.filter(is_default=True).first()
    if not price_list:
        return  # No default price list — nothing to sync

    PriceListItem.objects.update_or_create(
        price_list=price_list,
        product_id=menu_item.product_id,
        defaults={
            "product_name":  menu_item.name,
            "selling_price": menu_item.price,
        },
    )


# =============================== POS SESSION ===============================

def open_pos_session(
    *,
    employee: Employee,
    opening_cash: Decimal | float | str = 0,
) -> POSSession:

    if POSSession.objects.filter(employee=employee, is_active=True).exists():
        raise ValidationError("Employee already has an active POS session.")

    session = POSSession(
        employee=employee,
        opening_cash=Decimal(str(opening_cash)),
    )
    session.full_clean()
    session.save()
    return session


def close_pos_session(
    *,
    session_id: int,
    closing_cash: Decimal | float | str,
) -> POSSession:

    session = get_object_or_404(POSSession, id=session_id, is_active=True)
    session.closing_cash = Decimal(str(closing_cash))
    session.closed_at    = timezone.now()
    session.is_active    = False
    session.full_clean()
    session.save()
    return session


# =============================== RECEIPT ===============================

@transaction.atomic
def create_receipt(
    *,
    session: POSSession,
    created_by: Employee,
    discount: Decimal | float | str = 0,
    table_note: str = "",
) -> Receipt:
    receipt = Receipt(
        receipt_number="PENDING",
        session=session,
        created_by=created_by,
        discount=Decimal(str(discount)),
        table_note=table_note,
        status=Receipt.DRAFT,
    )
    receipt.save()
    receipt.receipt_number = (
        f"RCP-{datetime.now().strftime('%Y%m%d')}-{str(receipt.id).zfill(4)}"
    )
    receipt.save(update_fields=["receipt_number"])
    return receipt


# =============================== ORDERS ===============================

@transaction.atomic
def create_order(
    *,
    receipt: Receipt,
    created_by: Employee,
) -> Order:
    order = Order(receipt=receipt, created_by=created_by)
    order.full_clean()
    order.save()
    return order


@transaction.atomic
def add_order_item(
    *,
    order: Order,
    product: Product,
    quantity: float,
    final_price: Decimal | float | str,
    sold_by: Employee,
    price_override_reason: str | None = None,
    menu_item: MenuItem | None = None,
) -> OrderItem:
    """
    Adds an inventory-linked product to an order.

    Price resolution order:
    1. Look up PriceListItem for this product in the default PriceList.
       If found → listed_price = PriceListItem.selling_price
    2. If not found → listed_price = final_price (no override)

    Since _sync_price_list_item is called whenever a MenuItem is
    created or updated, PriceListItem will always exist for any
    inventory-linked menu item that has been priced by staff.
    So in practice listed_price = MenuItem.price = final_price
    and price_overridden = False for all normal sales.

    Price override is only triggered if a waiter manually passes
    a different final_price than what's in the PriceList.
    """
    if quantity <= 0:
        raise ValidationError("Quantity must be greater than zero.")

    final_price = Decimal(str(final_price)).quantize(TWO, rounding=ROUND_HALF_UP)
    qty         = Decimal(str(quantity)).quantize(TWO, rounding=ROUND_HALF_UP)

    from .models import PriceListItem, PriceList
    try:
        default_price_list = PriceList.objects.get(is_default=True)
        price_list_item    = PriceListItem.objects.get(
            price_list=default_price_list,
            product_id=product.id,
        )
        listed_price = price_list_item.selling_price.quantize(TWO, rounding=ROUND_HALF_UP)
        price_list   = default_price_list
    except (PriceList.DoesNotExist, PriceListItem.DoesNotExist):
        # No price list entry — treat final_price as the official price
        listed_price = final_price
        price_list   = PriceList.objects.filter(is_default=True).first()
        if not price_list:
            raise ValidationError(
                "No default price list found. Please configure one before selling."
            )

    price_overridden = final_price != listed_price

    if price_overridden and not price_override_reason:
        raise ValidationError("Price override requires a reason.")

    line_total = (final_price * qty).quantize(TWO, rounding=ROUND_HALF_UP)

    item = OrderItem(
        order=order,
        product_id=product.id,
        product_name=product.name,
        price_list=price_list,
        quantity=qty,
        listed_price=listed_price,
        final_price=final_price,
        price_overridden=price_overridden,
        price_override_reason=price_override_reason or "",
        sold_by=sold_by,
        line_total=line_total,
        menu_item=menu_item,
    )
    item.full_clean()
    item.save()
    return item


@transaction.atomic
def add_menu_order_item(
    *,
    order: Order,
    menu_item: MenuItem,
    quantity: float,
    sold_by: Employee,
) -> OrderItem:
    """
    Adds a manual menu item (no inventory product) to an order.
    Uses the menu item's price directly.
    No PriceListItem lookup, no stock deduction.
    product_id stored as 0 (sentinel — no real inventory product).
    """
    if quantity <= 0:
        raise ValidationError("Quantity must be greater than zero.")

    from .models import PriceList
    price_list = PriceList.objects.filter(is_default=True).first()
    if not price_list:
        raise ValidationError("No default price list found.")

    final_price = menu_item.price.quantize(TWO, rounding=ROUND_HALF_UP)
    qty         = Decimal(str(quantity)).quantize(TWO, rounding=ROUND_HALF_UP)
    line_total  = (final_price * qty).quantize(TWO, rounding=ROUND_HALF_UP)

    item = OrderItem(
        order=order,
        product_id=0,
        product_name=menu_item.name,
        price_list=price_list,
        quantity=qty,
        listed_price=final_price,
        final_price=final_price,
        price_overridden=False,
        price_override_reason="",
        sold_by=sold_by,
        line_total=line_total,
        menu_item=menu_item,
    )
    item.full_clean()
    item.save()
    return item


# =============================== SUBMIT ORDER ===============================

@transaction.atomic
def submit_order(
    *,
    receipt: Receipt,
    performed_by: Employee,
    emit_stock: bool = True,
) -> Receipt:
    """
    Waiter submits a DRAFT receipt → PENDING.
    - Calculates subtotal/total from all orders that have items.
    - Attempts stock deduction per inventory-linked item inside savepoints.
    - Manual menu items (product_id=0) skip stock deduction.
    - Stock failure never blocks submission.
    """

    if receipt.status != Receipt.DRAFT:
        raise ValidationError(
            f"Only DRAFT receipts can be submitted. Current status: {receipt.status}"
        )

    # Re-fetch orders fresh — bypasses stale ORM instance cache
    # from before createOrder/addOrderItem were called.
    all_orders = list(
        Order.objects
        .filter(receipt_id=receipt.pk)
        .prefetch_related("items")
        .order_by("-created_at")
    )

    # Only process orders that have items — previous recalled orders
    # (empty after recall) are kept for audit but excluded from totals.
    orders = [o for o in all_orders if o.items.all().count() > 0]

    if not orders:
        raise ValidationError("Receipt has no items.")

    subtotal = Decimal("0.00")

    for order in orders:
        for item in order.items.all():
            subtotal += (item.final_price * item.quantity).quantize(
                TWO, rounding=ROUND_HALF_UP
            )

            # Skip stock deduction for manual menu items (sentinel product_id = 0)
            if item.product_id == 0:
                continue

            inventory_deducted = False
            inventory_error    = None
            product            = None

            try:
                product = Product.objects.get(pk=item.product_id)
            except Product.DoesNotExist:
                inventory_error = f"Product {item.product_id} not found in inventory"

            if emit_stock and product is not None and product.auto_deduct_on_sale:
                try:
                    with transaction.atomic():
                        remove_stock(
                            product=product,
                            quantity=float(item.quantity),
                            reason=StockMovement.SALE,
                            performed_by=performed_by,
                            group_id=str(receipt.id),
                        )
                        inventory_deducted = True
                except ValidationError as exc:
                    inventory_error = str(exc)
                except Exception as exc:
                    inventory_error = f"Unexpected error: {str(exc)}"

            if product is not None:
                POSStockMovement.objects.create(
                    receipt=receipt,
                    product=product,
                    quantity=item.quantity,
                    deducted_from_inventory=inventory_deducted,
                    notes=inventory_error or "",
                    performed_by=performed_by,
                )

    subtotal = subtotal.quantize(TWO, rounding=ROUND_HALF_UP)

    receipt.subtotal     = subtotal
    receipt.total        = (subtotal - receipt.discount).quantize(TWO, rounding=ROUND_HALF_UP)
    receipt.status       = Receipt.PENDING
    receipt.submitted_at = timezone.now()
    receipt.full_clean()
    receipt.save()
    return receipt


# =============================== RECALL ORDER ===============================

@transaction.atomic
def recall_order(
    *,
    receipt: Receipt,
    recalled_by: Employee,
) -> Receipt:

    if receipt.status != Receipt.PENDING:
        raise ValidationError(
            f"Only PENDING receipts can be recalled. Current status: {receipt.status}"
        )

    stock_movements = POSStockMovement.objects.filter(
        receipt=receipt,
        deducted_from_inventory=True,
    ).select_related("product")

    for movement in stock_movements:
        try:
            with transaction.atomic():
                from inventory.services import add_stock
                add_stock(
                    product=movement.product,
                    quantity=float(movement.quantity),
                    reason=StockMovement.ADJUSTMENT,
                    performed_by=recalled_by,
                    notes=f"Stock reversal — order recalled: {receipt.receipt_number}",
                )
                movement.deducted_from_inventory = False
                movement.notes = "Reversed on recall"
                movement.save(update_fields=["deducted_from_inventory", "notes"])
        except Exception:
            movement.notes = "Reversal failed on recall"
            movement.save(update_fields=["notes"])

    receipt.status       = Receipt.DRAFT
    receipt.submitted_at = None
    receipt.subtotal     = Decimal("0.00")
    receipt.total        = Decimal("0.00")
    receipt.save(update_fields=["status", "submitted_at", "subtotal", "total"])
    return receipt


# =============================== PAYMENTS ===============================

@transaction.atomic
def accept_payment(
    *,
    receipt_id: int,
    amount: Decimal | float | str,
    method: str,
    received_by: Employee,
) -> Payment:

    amount = Decimal(str(amount)).quantize(TWO, rounding=ROUND_HALF_UP)
    if amount <= 0:
        raise ValidationError("Payment amount must be greater than zero.")

    receipt = Receipt.objects.select_for_update().get(pk=receipt_id)

    if receipt.status not in {Receipt.PENDING, Receipt.OPEN}:
        raise ValidationError(
            f"Cannot accept payment on a {receipt.status} receipt."
        )

    paid    = sum(p.amount for p in receipt.payments.all())
    balance = (receipt.total - paid).quantize(TWO, rounding=ROUND_HALF_UP)

    if amount > balance:
        raise ValidationError("Payment exceeds remaining balance.")

    payment = Payment(
        receipt=receipt,
        amount=amount,
        method=method,
        received_by=received_by,
    )
    payment.full_clean()
    payment.save()

    receipt.status = Receipt.PAID if amount == balance else Receipt.OPEN
    receipt.save(update_fields=["status"])
    return payment


# =============================== CREDIT ===============================

@transaction.atomic
def create_credit_account(
    *,
    receipt: Receipt,
    customer_name: str,
    customer_phone: str | None,
    due_date,
    approved_by: Employee,
) -> CreditAccount:

    if receipt.status not in {Receipt.PENDING, Receipt.OPEN}:
        raise ValidationError(
            f"Cannot create credit on a {receipt.status} receipt."
        )

    credit = CreditAccount(
        receipt=receipt,
        customer_name=customer_name,
        customer_phone=customer_phone or "",
        credit_amount=receipt.total,
        due_date=due_date,
        approved_by=approved_by,
    )
    credit.full_clean()
    credit.save()

    receipt.status = Receipt.CREDIT
    receipt.save(update_fields=["status"])
    return credit


# =============================== SETTLE CREDIT ===============================

@transaction.atomic
def settle_credit(
    *,
    credit_id: int,
    amount: Decimal | float | str,
    method: str,
    settled_by: Employee,
) -> Payment:

    credit  = get_object_or_404(CreditAccount, pk=credit_id)
    receipt = credit.receipt

    if credit.is_settled:
        raise ValidationError("This credit account is already settled.")

    amount = Decimal(str(amount)).quantize(TWO, rounding=ROUND_HALF_UP)
    if amount <= 0:
        raise ValidationError("Amount must be greater than zero.")

    paid    = sum(p.amount for p in receipt.payments.all())
    balance = (receipt.total - paid).quantize(TWO, rounding=ROUND_HALF_UP)

    if amount > balance:
        raise ValidationError("Amount exceeds outstanding credit balance.")

    payment = Payment(
        receipt=receipt,
        amount=amount,
        method=method,
        received_by=settled_by,
    )
    payment.full_clean()
    payment.save()

    if amount == balance:
        credit.is_settled = True
        credit.settled_by = settled_by
        credit.settled_at = timezone.now()
        credit.save(update_fields=["is_settled", "settled_by", "settled_at"])
        receipt.status = Receipt.PAID
        receipt.save(update_fields=["status"])

    return payment


# =============================== REFUNDS ===============================

@transaction.atomic
def refund_receipt(
    *,
    receipt_id: int,
    reason: str,
    refunded_by: Employee,
) -> Receipt:

    receipt = Receipt.objects.select_for_update().get(pk=receipt_id)

    if receipt.status not in {Receipt.PAID, Receipt.CREDIT}:
        raise ValidationError("Only paid or credit receipts can be refunded.")

    receipt.status        = Receipt.REFUNDED
    receipt.refund_reason = reason
    receipt.refunded_by   = refunded_by
    receipt.refunded_at   = timezone.now()
    receipt.save()
    return receipt


# =============================== MENU ===============================

def create_menu_item(
    *,
    name: str,
    emoji: str,
    price: Decimal | float | str,
    is_pinned: bool = False,
    product_id: int | None = None,
) -> MenuItem:
    """
    Creates a MenuItem. If product_id is given, links to that inventory
    product and syncs the price into the default PriceList so that
    add_order_item finds a matching PriceListItem and records the
    correct listed_price with no override flag.
    """
    if product_id:
        try:
            product = InventoryProduct.objects.get(pk=product_id)
            # Allow update if MenuItem already exists (e.g. was zero-priced)
            # hasattr check uses the reverse OneToOne descriptor
            if hasattr(product, "menu_item") and product.menu_item is not None:
                raise ValidationError("This product already has a menu item.")
        except InventoryProduct.DoesNotExist:
            raise ValidationError("Product not found.")
    else:
        product = None

    item = MenuItem(
        name=name,
        emoji=emoji,
        price=Decimal(str(price)).quantize(TWO, rounding=ROUND_HALF_UP),
        is_pinned=is_pinned,
        product=product,
    )
    item.full_clean()
    item.save()

    # Sync price into PriceListItem so listed_price is correct at sale time
    _sync_price_list_item(item)

    return item


def update_menu_item(
    *,
    item_id: int,
    name: str | None = None,
    emoji: str | None = None,
    price: Decimal | float | str | None = None,
    is_pinned: bool | None = None,
    is_available: bool | None = None,
) -> MenuItem:
    """
    Updates a MenuItem. If price changes, syncs the new price into
    the default PriceListItem so future sales reflect the updated price.
    """
    item = get_object_or_404(MenuItem, pk=item_id)

    if name         is not None: item.name         = name
    if emoji        is not None: item.emoji        = emoji
    if price        is not None: item.price        = Decimal(str(price)).quantize(TWO, rounding=ROUND_HALF_UP)
    if is_pinned    is not None: item.is_pinned    = is_pinned
    if is_available is not None: item.is_available = is_available

    item.full_clean()
    item.save()

    # Re-sync price into PriceListItem whenever anything changes
    # (name change also updates product_name on PriceListItem)
    _sync_price_list_item(item)

    return item


def delete_menu_item(*, item_id: int) -> bool:
    """
    Deletes a manual menu item.
    Inventory-linked items cannot be deleted — mark unavailable instead.
    Does NOT delete the PriceListItem — historical price data is preserved.
    """
    item = get_object_or_404(MenuItem, pk=item_id)
    if item.product is not None:
        raise ValidationError(
            "Cannot delete an inventory-linked menu item. "
            "Mark it unavailable instead."
        )
    item.delete()
    return True


def get_menu_with_frequency(limit: int = 8) -> list:
    """
    Returns all available menu items with price > 0, annotated with
    order frequency, sorted by pin status then frequency.
    Zero-priced items are excluded — they appear in unpricedInventoryItems
    instead and won't show on the waiter's menu until priced.
    """
    from django.db.models import Count
    items = (
        MenuItem.objects
        .filter(is_available=True, price__gt=Decimal("0.00"))
        .annotate(
            order_count=Count(
                "product__pos_movements__receipt",
                distinct=True,
            )
        )
        .order_by("-is_pinned", "-order_count", "name")
    )
    return list(items)