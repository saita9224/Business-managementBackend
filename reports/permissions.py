# reports/permissions.py

"""
Reports permissions.

These permissions control access to read-only analytical
and reporting features across the system.

They are auto-loaded by employees/permission_loader.py
into the Permission table.
"""

PERMISSIONS = {

    # ===============================
    # SALES REPORTS
    # ===============================
    "reports.view_all_sales",      # View all sales (admin / manager)
    "reports.view_own_sales",      # View own receipts only (cashier)

    # ===============================
    # SALES ANALYTICS (TRENDS)
    # ===============================
    "reports.view_sales_trends",   # Daily / monthly trends, charts

    # ===============================
    # STAFF PERFORMANCE
    # ===============================
    "reports.view_staff_sales",    # Per-staff sales summaries

    # ===============================
    # POS SESSION REPORTS
    # ===============================
    "reports.view_session_sales",  # Per-shift reconciliation

    # ===============================
    # INVENTORY REPORTS (FUTURE)
    # ===============================
    "reports.view_inventory_reports",

    # ===============================
    # EXPENSE REPORTS (FUTURE)
    # ===============================
    "reports.view_expense_reports",

    # ===============================
    # FINANCIAL / PROFIT REPORTS (FUTURE)
    # ===============================
    "reports.view_financial_reports",
}
