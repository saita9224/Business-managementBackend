# expenses/permissions.py

"""
Permissions for the Expenses app.
permissions_loader.py loads these into the DB on startup.
"""

PERMISSIONS = {
    "expenses.view",
    "expenses.create",
    "expenses.update",
    "expenses.delete",
    "expenses.pay",
    "expenses.view_payments",
    "expenses.manage_suppliers",
}

PERMISSION_META = {
    "expenses.view":             ("View Expenses",       "Can view expense records and history"),
    "expenses.create":           ("Create Expenses",     "Can record new expense items"),
    "expenses.update":           ("Edit Expenses",       "Can modify existing expense records"),
    "expenses.delete":           ("Delete Expenses",     "Can delete expense records"),
    "expenses.pay":              ("Pay Expenses",        "Can record payments against expense balances"),
    "expenses.view_payments":    ("View Payments",       "Can view expense payment history"),
    "expenses.manage_suppliers": ("Manage Suppliers",    "Can add and manage supplier records"),
}