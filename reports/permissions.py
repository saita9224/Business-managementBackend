# reports/permissions.py

"""
Permissions for the Reports app.
permissions_loader.py loads these into the DB on startup.
"""

PERMISSIONS = {
    "reports.view_sales",
    "reports.view_expenses",
    "reports.view_inventory",
    "reports.view_payroll",
    "reports.view_attendance",
    "reports.view_credits",
}

PERMISSION_META = {
    "reports.view_sales":      ("Sales Reports",      "Can view sales summaries, trends and product performance"),
    "reports.view_expenses":   ("Expense Reports",    "Can view expense summaries and supplier breakdowns"),
    "reports.view_inventory":  ("Inventory Reports",  "Can view stock health and movement reports"),
    "reports.view_payroll":    ("Payroll Reports",    "Can view salary summaries and payment status"),
    "reports.view_attendance": ("Attendance Reports", "Can view employee attendance summaries"),
    "reports.view_credits":    ("Credit Reports",     "Can view credit exposure and overdue accounts"),
}