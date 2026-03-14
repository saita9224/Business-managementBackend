# POS/permissions.py

"""
POS permissions.
Auto-loaded by employees/permission_loader.py into the Permission table.
"""

PERMISSIONS = {

    # ── Session ───────────────────────────────────────────
    "pos.open_session",
    "pos.close_session",

    # ── Waiter: order & receipt ───────────────────────────
    "pos.create_order",       # Build cart, submit order (waiter)
    "pos.recall_order",       # Recall & edit own PENDING receipt
    "pos.merge_orders",       # Merge multiple orders under one receipt
    "pos.view_orders",        # View own past orders / receipts

    # ── Cashier: payment ──────────────────────────────────
    "pos.view_cashier",       # Access the cashier queue (PENDING receipts)
    "pos.accept_payment",     # Record CASH / MPESA / CARD payment
    "pos.partial_payment",    # Allow partial payments
    "pos.view_payments",      # View payment history

    # ── Credit ────────────────────────────────────────────
    "pos.create_credit",      # Mark receipt as credit (cashier)
    "pos.approve_credit",     # Manager-level credit approval
    "pos.settle_credit",      # Receive payment on a credit account

    # ── Price override ────────────────────────────────────
    "pos.override_price",     # Override item price

    # ── Refunds ───────────────────────────────────────────
    "pos.refund_order",       # Refund paid / credit receipt (manager)

    # ── Stock emission ────────────────────────────────────
    "pos.emit_stock",         # Reduce inventory when order is submitted

    # ── Menu management ───────────────────────────────────
    "pos.manage_menu",        # Add / edit / delete menu items
}