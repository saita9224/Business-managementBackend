# reports/services/sales.py

"""
Sales reporting service layer.

This module contains pure aggregation logic for sales reporting.
It does NOT know about GraphQL, REST, or views.

All functions return Python dictionaries or lists that can be safely
consumed by GraphQL resolvers, REST serializers, or admin dashboards.
"""

from decimal import Decimal
from django.db.models import Sum, Count

from POS.models import Receipt, OrderItem, Payment, POSSession
from employees.models import Employee


# ============================================================
# CORE AGGREGATION
# ============================================================

def get_sales_summary(receipts_queryset):
    """
    Core sales aggregation.

    This is the SINGLE source of truth for sales calculations.
    Every other function eventually calls this one.

    Args:
        receipts_queryset (QuerySet[Receipt]): Any filtered Receipt queryset.

    Returns:
        dict: {
            total_sales: Decimal,
            receipts_count: int,
            items_sold: int,
            payments: QuerySet[{method, amount}]
        }
    """

    # ---- RECEIPTS ----
    receipts_count = receipts_queryset.count()

    totals = receipts_queryset.aggregate(
        total_sales=Sum("total")
    )
    total_sales = totals["total_sales"] or Decimal("0.00")

    # ---- ITEMS SOLD ----
    items_sold = (
        OrderItem.objects
        .filter(order__receipt__in=receipts_queryset)
        .aggregate(total=Sum("quantity"))
        ["total"]
        or Decimal("0")
    )

    # ---- PAYMENTS BREAKDOWN ----
    payments = (
        Payment.objects
        .filter(receipt__in=receipts_queryset)
        .values("method")
        .annotate(amount=Sum("amount"))
    )

    return {
        "total_sales": total_sales,
        "receipts_count": receipts_count,
        "items_sold": items_sold,
        "payments": payments,
    }


# ============================================================
# DATE-BASED SUMMARY
# ============================================================

def get_sales_summary_by_date(receipts_queryset, start_date=None, end_date=None):
    """
    Sales summary filtered by receipt creation date.

    Args:
        receipts_queryset (QuerySet[Receipt])
        start_date (date | None): Inclusive start date
        end_date (date | None): Inclusive end date

    Returns:
        dict: Sales summary
    """

    if start_date:
        receipts_queryset = receipts_queryset.filter(
            created_at__date__gte=start_date
        )

    if end_date:
        receipts_queryset = receipts_queryset.filter(
            created_at__date__lte=end_date
        )

    return get_sales_summary(receipts_queryset)


# ============================================================
# POS SESSION-BASED SUMMARY
# ============================================================

def get_pos_session_sales_summary(session: POSSession):
    """
    Sales summary for a single POS session (shift).

    Args:
        session (POSSession)

    Returns:
        dict: Sales summary
    """

    receipts = Receipt.objects.filter(session=session)
    return get_sales_summary(receipts)


def get_pos_sessions_sales_summary(sessions_queryset):
    """
    Aggregated sales summary across multiple POS sessions.

    Args:
        sessions_queryset (QuerySet[POSSession])

    Returns:
        dict: Sales summary
    """

    receipts = Receipt.objects.filter(session__in=sessions_queryset)
    return get_sales_summary(receipts)


# ============================================================
# EMPLOYEE (STAFF) SUMMARY
# ============================================================

def get_employee_sales_summary(employee: Employee, receipts_queryset):
    """
    Sales summary for a single employee (cashier).

    Args:
        employee (Employee)
        receipts_queryset (QuerySet[Receipt])

    Returns:
        dict: Sales summary
    """

    employee_receipts = receipts_queryset.filter(created_by=employee)
    return get_sales_summary(employee_receipts)


def get_sales_summary_by_staff(receipts_queryset):
    """
    Per-staff sales breakdown.

    Groups receipts by staff member (created_by / issued_by)
    and returns one summary block per employee.

    Args:
        receipts_queryset (QuerySet[Receipt])

    Returns:
        list[dict]: [
            {
                employee_id,
                employee_name,
                total_sales,
                receipts_count,
                items_sold,
                payments
            }
        ]
    """

    staff_summaries = []

    # First-level aggregation (fast grouping)
    staff_receipts = (
        receipts_queryset
        .values("created_by", "created_by__name")
        .annotate(
            total_sales=Sum("total"),
            receipts_count=Count("id"),
        )
    )

    for staff in staff_receipts:
        staff_receipt_qs = receipts_queryset.filter(
            created_by=staff["created_by"]
        )

        # ---- ITEMS SOLD ----
        items_sold = (
            OrderItem.objects
            .filter(order__receipt__in=staff_receipt_qs)
            .aggregate(total=Sum("quantity"))
            ["total"] or Decimal("0")
        )

        # ---- PAYMENTS ----
        payments = (
            Payment.objects
            .filter(receipt__in=staff_receipt_qs)
            .values("method")
            .annotate(amount=Sum("amount"))
        )

        staff_summaries.append({
            "employee_id": staff["created_by"],
            "employee_name": staff["created_by__name"],
            "total_sales": staff["total_sales"] or Decimal("0.00"),
            "receipts_count": staff["receipts_count"],
            "items_sold": items_sold,
            "payments": payments,
        })

    return staff_summaries
