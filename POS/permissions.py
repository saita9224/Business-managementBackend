# pos/permissions.py

"""
POS permissions.
These are auto-loaded by employees/permission_loader.py
into the Permission table.
"""

PERMISSIONS = {

    # ===============================
    # POS SESSION
    # ===============================
    "pos.open_session",
    "pos.close_session",

    # ===============================
    # ORDER & RECEIPT
    # ===============================
    "pos.create_order",          # Create / save order
    "pos.merge_orders",          # Merge multiple orders under one receipt
    "pos.view_orders",           # View past orders / receipts

    # ===============================
    # PAYMENTS
    # ===============================
    "pos.accept_payment",        # Cash / Mpesa / Card
    "pos.partial_payment",       # Allow partial payments
    "pos.view_payments",

    # ===============================
    # CREDIT
    # ===============================
    "pos.create_credit",         # Allow order to go on credit
    "pos.approve_credit",        # Manager-level approval
    "pos.settle_credit",         # Receive credit payment

    # ===============================
    # PRICE OVERRIDE
    # ===============================
    "pos.override_price",        # Override item price (manager approval)

    # ===============================
    # REFUNDS
    # ===============================
    "pos.refund_order",          # Refund saved/paid orders (manager only)

    # ===============================
    # STOCK EMISSION
    # ===============================
    "pos.emit_stock",            # Reduce inventory on save order

}
