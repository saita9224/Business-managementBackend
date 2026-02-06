"""
Sales reporting GraphQL queries.

This module exposes read-only sales reports via GraphQL.
All heavy business logic lives in `reports/services/sales.py`.

ACCESS CONTROL (RBAC):
- reports.view_all_sales → can see all sales (admin / manager)
- reports.view_own_sales → can only see own receipts (cashiers)

Design principles:
- Queries only orchestrate data
- Services calculate numbers
- Permissions enforced at resolver level
"""

import strawberry
from typing import Optional, List
from datetime import date

from employees.decorators import permission_required
from POS.models import Receipt, POSSession

from reports.services.sales import (
    get_sales_summary_by_date,
    get_pos_session_sales_summary,
    get_sales_summary_by_staff,
)

# ======================================================
# GRAPHQL TYPES (LOCAL TO REPORTS)
# ======================================================

@strawberry.type
class PaymentBreakdownType:
    """
    Aggregated payment totals per payment method.
    Example: CASH → 12000, MPESA → 35000
    """
    method: str
    amount: float


@strawberry.type
class SalesSummaryType:
    """
    High-level sales summary.

    Used for:
    - global sales
    - per-session sales
    - per-user (own) sales
    """
    total_sales: float
    receipts_count: int
    items_sold: float
    payments: List[PaymentBreakdownType]


@strawberry.type
class StaffSalesSummaryType:
    """
    Sales summary grouped per staff member.
    Used for management reporting.
    """
    employee_id: strawberry.ID
    employee_name: str
    total_sales: float
    receipts_count: int
    items_sold: float
    payments: List[PaymentBreakdownType]


# ======================================================
# INTERNAL HELPERS
# ======================================================

def _map_sales_summary(summary: dict) -> SalesSummaryType:
    """
    Converts service-layer dict output into GraphQL type.
    """
    return SalesSummaryType(
        total_sales=summary["total_sales"],
        receipts_count=summary["receipts_count"],
        items_sold=summary["items_sold"],
        payments=[
            PaymentBreakdownType(
                method=p["method"],
                amount=p["amount"],
            )
            for p in summary["payments"]
        ],
    )


# ======================================================
# SALES QUERIES
# ======================================================

@strawberry.type
class SalesQueries:
    """
    Root sales-related queries.

    These queries are composed into the main GraphQL schema.
    """

    # --------------------------------------------------
    # 1. GLOBAL SALES SUMMARY (ADMIN / MANAGER)
    # --------------------------------------------------
    @strawberry.field
    @permission_required("reports.view_all_sales")
    def sales_summary(
        self,
        info,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> SalesSummaryType:
        """
        Returns overall sales summary across the system.

        Optional filters:
        - start_date
        - end_date

        Permission:
        - reports.view_all_sales
        """

        receipts = Receipt.objects.all()

        summary = get_sales_summary_by_date(
            receipts_queryset=receipts,
            start_date=start_date,
            end_date=end_date,
        )

        return _map_sales_summary(summary)

    # --------------------------------------------------
    # 2. MY SALES SUMMARY (CASHIER / STAFF)
    # --------------------------------------------------
    @strawberry.field
    @permission_required("reports.view_own_sales")
    def my_sales_summary(
        self,
        info,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> SalesSummaryType:
        """
        Returns sales summary for the currently logged-in employee.

        Uses:
        - Receipt.created_by = request.user

        Permission:
        - reports.view_own_sales
        """

        user = info.context.user

        receipts = Receipt.objects.filter(created_by=user)

        summary = get_sales_summary_by_date(
            receipts_queryset=receipts,
            start_date=start_date,
            end_date=end_date,
        )

        return _map_sales_summary(summary)

    # --------------------------------------------------
    # 3. POS SESSION SALES SUMMARY
    # --------------------------------------------------
    @strawberry.field
    @permission_required("reports.view_all_sales")
    def pos_session_sales_summary(
        self,
        info,
        session_id: strawberry.ID,
    ) -> SalesSummaryType:
        """
        Returns sales summary for a single POS session (shift).

        Useful for:
        - shift reconciliation
        - cashier handover
        - audit reviews

        Permission:
        - reports.view_all_sales
        """

        session = POSSession.objects.get(id=session_id)

        summary = get_pos_session_sales_summary(session)

        return _map_sales_summary(summary)

    # --------------------------------------------------
    # 4. SALES SUMMARY BY STAFF (MANAGEMENT)
    # --------------------------------------------------
    @strawberry.field
    @permission_required("reports.view_all_sales")
    def sales_summary_by_staff(
        self,
        info,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[StaffSalesSummaryType]:
        """
        Returns sales grouped per employee.

        Used for:
        - staff performance
        - accountability
        - incentive calculations

        Permission:
        - reports.view_all_sales
        """

        receipts = Receipt.objects.all()

        if start_date:
            receipts = receipts.filter(created_at__date__gte=start_date)
        if end_date:
            receipts = receipts.filter(created_at__date__lte=end_date)

        staff_summaries = get_sales_summary_by_staff(receipts)

        return [
            StaffSalesSummaryType(
                employee_id=s["employee_id"],
                employee_name=s["employee_name"],
                total_sales=s["total_sales"],
                receipts_count=s["receipts_count"],
                items_sold=s["items_sold"],
                payments=[
                    PaymentBreakdownType(
                        method=p["method"],
                        amount=p["amount"],
                    )
                    for p in s["payments"]
                ],
            )
            for s in staff_summaries
        ]
