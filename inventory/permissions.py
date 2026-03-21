# inventory/permissions.py

"""
Permissions for the Inventory app.
permissions_loader.py loads these into the DB on startup.
"""

PERMISSIONS = {
    "inventory.product.view",
    "inventory.product.create",
    "inventory.product.update",
    "inventory.product.delete",
    "inventory.stock.view",
    "inventory.stock.in",
    "inventory.stock.out",
    "inventory.stock.adjust",
    "inventory.stock.view_history",
    "inventory.stock.reconcile",
    "inventory.stock.view_discrepancy",
}

PERMISSION_META = {
    "inventory.product.view":           ("View Products",           "Can view the product list and stock levels"),
    "inventory.product.create":         ("Create Products",         "Can add new inventory products"),
    "inventory.product.update":         ("Edit Products",           "Can update product details and POS flag"),
    "inventory.product.delete":         ("Delete Products",         "Can remove products from inventory"),
    "inventory.stock.view":             ("View Stock Movements",    "Can view stock movement records"),
    "inventory.stock.in":               ("Add Stock",               "Can record incoming stock purchases and returns"),
    "inventory.stock.out":              ("Deduct Stock",            "Can manually deduct stock"),
    "inventory.stock.adjust":           ("Adjust Stock",            "Can submit and approve stock reconciliations"),
    "inventory.stock.view_history":     ("Full Audit Trail",        "Can view complete inventory audit history"),
    "inventory.stock.reconcile":        ("Reconcile Stock",         "Can perform physical stock counts"),
    "inventory.stock.view_discrepancy": ("View Discrepancies",      "Can view stock discrepancy reports"),
}