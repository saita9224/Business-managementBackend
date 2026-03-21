# POS/permissions.py

"""
Permissions for the POS app.
permissions_loader.py loads these into the DB on startup.
"""

PERMISSIONS = {
    "pos.open_session",
    "pos.close_session",
    "pos.create_order",
    "pos.recall_order",
    "pos.merge_orders",
    "pos.view_orders",
    "pos.view_cashier",
    "pos.accept_payment",
    "pos.partial_payment",
    "pos.view_payments",
    "pos.create_credit",
    "pos.approve_credit",
    "pos.settle_credit",
    "pos.override_price",
    "pos.refund_order",
    "pos.emit_stock",
    "pos.manage_menu",
}

PERMISSION_META = {
    "pos.open_session":   ("Open POS Session",    "Can open a new POS session at the start of a shift"),
    "pos.close_session":  ("Close POS Session",   "Can close a POS session at the end of a shift"),
    "pos.create_order":   ("Create Orders",        "Can build a cart and submit orders to the cashier"),
    "pos.recall_order":   ("Recall Orders",        "Can recall and edit own pending orders"),
    "pos.merge_orders":   ("Merge Orders",         "Can merge multiple orders under one receipt"),
    "pos.view_orders":    ("View Orders",          "Can view own past orders and receipts"),
    "pos.view_cashier":   ("Cashier Queue",        "Can access the cashier queue and open receipts"),
    "pos.accept_payment": ("Accept Payments",      "Can record cash, M-Pesa, and card payments"),
    "pos.partial_payment":("Partial Payments",     "Can accept partial payments on a receipt"),
    "pos.view_payments":  ("View Payments",        "Can view payment history for receipts"),
    "pos.create_credit":  ("Create Credit",        "Can mark a receipt as credit for a customer"),
    "pos.approve_credit": ("Approve Credit",       "Can approve credit accounts (manager level)"),
    "pos.settle_credit":  ("Settle Credit",        "Can receive payment on outstanding credit accounts"),
    "pos.override_price": ("Override Price",       "Can override item prices when adding to an order"),
    "pos.refund_order":   ("Refund Orders",        "Can issue refunds on paid or credit receipts"),
    "pos.emit_stock":     ("Auto Deduct Stock",    "Can trigger automatic inventory deduction on sale"),
    "pos.manage_menu":    ("Manage Menu",          "Can add, edit, and remove items from the POS menu"),
}