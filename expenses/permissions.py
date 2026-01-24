# expenses/permissions.py



# ────────────────────────────────────────────────
#  SOURCE-OF-TRUTH PERMISSIONS FOR EXPENSES APP
# ────────────────────────────────────────────────
# These are inserted into the DB by the global loader.
#
# Pattern: "expenses.action"
# Example: "expenses.create", "expenses.pay", etc.
# ────────────────────────────────────────────────

EXPENSE_PERMISSIONS = [
    # CRUD on Expense Items
    "expenses.create",
    "expenses.update",
    "expenses.delete",
    "expenses.view",

    # Payments
    "expenses.pay",
    "expenses.view_payments",

    # Supplier management
    "expenses.manage_suppliers",
]

PERMISSIONS = EXPENSE_PERMISSIONS

