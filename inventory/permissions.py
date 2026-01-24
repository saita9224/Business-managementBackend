from employees.decorators import permission_required

"""
Inventory permissions.

This file defines ALL permissions for the Inventory app.
They are automatically inserted into the database
by the global permission loader during startup.
"""

# ────────────────────────────────────────────────
# PRODUCT PERMISSIONS
# ────────────────────────────────────────────────
INVENTORY_PERMISSIONS = [
    # Products
    "inventory.product.view",
    "inventory.product.create",
    "inventory.product.update",
    "inventory.product.delete",

    # Stock movements (audit-sensitive)
    "inventory.stock.view",
    "inventory.stock.in",
    "inventory.stock.out",
    "inventory.stock.adjust",

    # Reports / visibility
    "inventory.stock.view_history",
]

PERMISSIONS = INVENTORY_PERMISSIONS