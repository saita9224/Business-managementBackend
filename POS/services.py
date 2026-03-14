# POS/services.py

from decimal import Decimal
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
    session.closed_at = timezone.now()
    session.is_active = False
    session.full_clean()
    session.save()
    return session


# =============================== RECEIPT CREATION ===============================

@transaction.atomic
def create_receipt(
    *,
    session: POSSession,
    created_by: Employee,
    discount: Decimal | float | str = 0,
    table_note: str = "",
) -> Receipt:
    """
    Creates a new DRAFT receipt under the given session.
    Receipt number generated after save to include DB-assigned ID.
    Format: RCP-YYYYMMDD-{id zero-padded to 4 digits}
    """
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
) -> OrderItem:

    if quantity <= 0:
        raise ValidationError("Quantity must be greater than zero.")

    final_price = Decimal(str(final_price))

    from .models import PriceListItem, PriceList
    try:
        default_price_list = PriceList.objects.get(is_default=True)
        price_list_item = PriceListItem.objects.get(
            price_list=default_price_list,
            product_id=product.id,
        )
        listed_price = price_list_item.selling_price
        price_list = default_price_list
    except (PriceList.DoesNotExist, PriceListItem.DoesNotExist):
        listed_price = final_price
        price_list = PriceList.objects.filter(is_default=True).first()
        if not price_list:
            raise ValidationError(
                "No default price list found. Please configure one before selling."
            )

    price_overridden = final_price != listed_price

    if price_overridden and not price_override_reason:
        raise ValidationError("Price override requires a reason.")

    line_total = final_price * Decimal(str(quantity))

    item = OrderItem(
        order=order,
        product_id=product.id,
        product_name=product.name,
        price_list=price_list,
        quantity=Decimal(str(quantity)),
        listed_price=listed_price,
        final_price=final_price,
        price_overridden=price_overridden,
        price_override_reason=price_override_reason or "",
        sold_by=sold_by,
        line_total=line_total,
    )
    item.full_clean()
    item.save()
    return item


# =============================== SUBMIT ORDER (WAITER) ===============================

@transaction.atomic
def submit_order(
    *,
    receipt: Receipt,
    performed_by: Employee,
    emit_stock: bool = True,
) -> Receipt:

    if receipt.status != Receipt.DRAFT:
        raise ValidationError(
            f"Only DRAFT receipts can be submitted. Current status: {receipt.status}"
        )

    # ── Debug: print what we find in the DB at submit time ──
    from django.db import connection
    print(f"\n=== SUBMIT ORDER DEBUG ===")
    print(f"Receipt ID: {receipt.pk}")
    print(f"Receipt status: {receipt.status}")

    # Direct DB count — bypasses ALL ORM caching
    order_count = Order.objects.filter(receipt_id=receipt.pk).count()
    print(f"Orders in DB for this receipt: {order_count}")

    if order_count > 0:
        for o in Order.objects.filter(receipt_id=receipt.pk):
            item_count = OrderItem.objects.filter(order_id=o.pk).count()
            print(f"  Order {o.pk}: {item_count} items")
            for i in OrderItem.objects.filter(order_id=o.pk):
                print(f"    Item: {i.product_name} x {i.quantity} @ {i.final_price}")

    print(f"=========================\n")

    orders = list(
        Order.objects
        .filter(receipt_id=receipt.pk)
        .prefetch_related("items")
    )

    if not orders:
        raise ValidationError("Receipt has no orders.")

    subtotal = Decimal("0.00")

    for order in orders:
        items = list(order.items.all())
        print(f"Order {order.pk} has {len(items)} items in prefetch")
        for item in items:
            subtotal += item.final_price * item.quantity
            print(f"  Adding: {item.product_name} {item.final_price} x {item.quantity}")

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

    print(f"Final subtotal: {subtotal}")

    receipt.subtotal     = subtotal
    receipt.total        = subtotal - receipt.discount
    receipt.status       = Receipt.PENDING
    receipt.submitted_at = timezone.now()
    receipt.full_clean()
    receipt.save()
    return receipt


# =============================== RECALL ORDER (WAITER) ===============================

@transaction.atomic
def recall_order(
    *,
    receipt: Receipt,
    recalled_by: Employee,
) -> Receipt:
    """
    Waiter action — recalls a PENDING receipt back to DRAFT so items
    can be added or modified before re-submitting.

    Only the original creator can recall (enforced in the mutation).
    Reverses any stock deductions that were made on submit.
    """

    if receipt.status != Receipt.PENDING:
        raise ValidationError(
            f"Only PENDING receipts can be recalled. Current status: {receipt.status}"
        )

    # ── Reverse stock deductions that were emitted on submit ──
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
            # Reversal failure is logged but does not block recall
            movement.notes = "Reversal failed on recall"
            movement.save(update_fields=["notes"])

    receipt.status       = Receipt.DRAFT
    receipt.submitted_at = None
    receipt.subtotal     = Decimal("0.00")
    receipt.total        = Decimal("0.00")
    receipt.save(update_fields=["status", "submitted_at", "subtotal", "total"])
    return receipt


# =============================== PAYMENTS (CASHIER) ===============================

@transaction.atomic
def accept_payment(
    *,
    receipt_id: int,
    amount: Decimal | float | str,
    method: str,
    received_by: Employee,
) -> Payment:
    """
    Cashier action — records a payment against a PENDING or OPEN receipt.
    PENDING → OPEN on first partial payment.
    OPEN / PENDING → PAID when balance reaches zero.
    """

    amount  = Decimal(str(amount))
    if amount <= 0:
        raise ValidationError("Payment amount must be greater than zero.")

    receipt = Receipt.objects.select_for_update().get(pk=receipt_id)

    if receipt.status not in {Receipt.PENDING, Receipt.OPEN}:
        raise ValidationError(
            f"Cannot accept payment on a {receipt.status} receipt."
        )

    paid    = sum(p.amount for p in receipt.payments.all())
    balance = receipt.total - paid

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

    if amount == balance:
        receipt.status = Receipt.PAID
    else:
        receipt.status = Receipt.OPEN

    receipt.save(update_fields=["status"])
    return payment


# =============================== CREDIT (CASHIER) ===============================

@transaction.atomic
def create_credit_account(
    *,
    receipt: Receipt,
    customer_name: str,
    customer_phone: str | None,
    due_date,
    approved_by: Employee,
) -> CreditAccount:
    """
    Cashier action — defers a PENDING receipt to a credit account.
    """

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
    """
    Cashier action — receives payment against an unsettled credit account.
    Records a Payment against the original receipt.
    Marks CreditAccount.is_settled = True when fully paid.
    """

    credit  = get_object_or_404(CreditAccount, pk=credit_id)
    receipt = credit.receipt

    if credit.is_settled:
        raise ValidationError("This credit account is already settled.")

    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValidationError("Amount must be greater than zero.")

    # Total already paid towards this receipt (could be partial payments before credit)
    paid    = sum(p.amount for p in receipt.payments.all())
    balance = receipt.total - paid

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
        credit.is_settled  = True
        credit.settled_by  = settled_by
        credit.settled_at  = timezone.now()
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

    receipt.status      = Receipt.REFUNDED
    receipt.refund_reason = reason
    receipt.refunded_by = refunded_by
    receipt.refunded_at = timezone.now()
    receipt.save()
    return receipt


# =============================== MENU ===============================

def sync_inventory_to_menu() -> list[MenuItem]:
    """
    Auto-creates MenuItem records for every inventory product with
    auto_deduct_on_sale=True that has no existing MenuItem.
    Idempotent — safe to call on every menu query.
    """
    products = InventoryProduct.objects.filter(
        auto_deduct_on_sale=True,
        menu_item__isnull=True,
    )
    created = []
    for product in products:
        item = MenuItem.objects.create(
            name=product.name,
            emoji="🛒",
            price=Decimal("0.00"),
            product=product,
            is_available=True,
            is_pinned=False,
        )
        created.append(item)
    return created


def create_menu_item(
    *,
    name: str,
    emoji: str,
    price: Decimal | float | str,
    is_pinned: bool = False,
    product_id: int | None = None,
) -> MenuItem:

    if product_id:
        try:
            product = InventoryProduct.objects.get(pk=product_id)
            if hasattr(product, "menu_item"):
                raise ValidationError("This product already has a menu item.")
        except InventoryProduct.DoesNotExist:
            raise ValidationError("Product not found.")
    else:
        product = None

    item = MenuItem(
        name=name,
        emoji=emoji,
        price=Decimal(str(price)),
        is_pinned=is_pinned,
        product=product,
    )
    item.full_clean()
    item.save()
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
    item = get_object_or_404(MenuItem, pk=item_id)
    if name        is not None: item.name        = name
    if emoji       is not None: item.emoji       = emoji
    if price       is not None: item.price       = Decimal(str(price))
    if is_pinned   is not None: item.is_pinned   = is_pinned
    if is_available is not None: item.is_available = is_available
    item.full_clean()
    item.save()
    return item


def delete_menu_item(*, item_id: int) -> bool:
    item = get_object_or_404(MenuItem, pk=item_id)
    if item.product is not None:
        raise ValidationError(
            "Cannot delete an inventory-linked menu item. "
            "Mark it unavailable instead."
        )
    item.delete()
    return True


def get_menu_with_frequency(limit: int = 8) -> list:
    from django.db.models import Count
    items = (
        MenuItem.objects
        .filter(is_available=True)
        .annotate(
            order_count=Count(
                "product__pos_movements__receipt",
                distinct=True,
            )
        )
        .order_by("-is_pinned", "-order_count", "name")
    )
    return list(items)