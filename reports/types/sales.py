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

from django.db.models import Sum, Count
from django.db.models.functions import TruncDate

from employees.decorators import permission_required
from POS.models import Receipt, POSSession

from reports.services.sales import (
    get_sales_summary_by_date,
    get_pos_session_sales_summary,
    get_sales_summary_by_staff,
)

# ======================================================
# GRAPHQL TYPES
# ======================================================

@strawberry.type
class PaymentBreakdownType:
    method: str
    amount: float


@strawberry.type
class SalesSummaryType:
    total_sales: float
    receipts_count: int
    items_sold: float
    payments: List[PaymentBreakdownType]


@strawberry.type
class StaffSalesSummaryType:
    employee_id: strawberry.ID
    employee_name: str
    total_sales: float
    receipts_count: int
    items_sold: float
    payments: List[PaymentBreakdownType]


@strawberry.type
class DailySalesTrendType:
    """
    Sales metrics aggregated per day.
    Used for charts and trend analysis.
    """
    date: date
    total_sales: float
    receipts_count: int
    items_sold: float


# ======================================================
# INTERNAL HELPERS
# ======================================================

def _map_sales_summary(summary: dict) -> SalesSummaryType:
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

    # --------------------------------------------------
    # 1. GLOBAL SALES SUMMARY
    # --------------------------------------------------
    @strawberry.field
    @permission_required("reports.view_all_sales")
    def sales_summary(
        self,
        info,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> SalesSummaryType:

        receipts = Receipt.objects.all()

        summary = get_sales_summary_by_date(
            receipts_queryset=receipts,
            start_date=start_date,
            end_date=end_date,
        )

        return _map_sales_summary(summary)

    # --------------------------------------------------
    # 2. MY SALES SUMMARY
    # --------------------------------------------------
    @strawberry.field
    @permission_required("reports.view_own_sales")
    def my_sales_summary(
        self,
        info,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> SalesSummaryType:

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

        session = POSSession.objects.get(id=session_id)

        summary = get_pos_session_sales_summary(session)

        return _map_sales_summary(summary)

    # --------------------------------------------------
    # 4. SALES SUMMARY BY STAFF
    # --------------------------------------------------
    @strawberry.field
    @permission_required("reports.view_all_sales")
    def sales_summary_by_staff(
        self,
        info,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[StaffSalesSummaryType]:

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

    # --------------------------------------------------
    # 5. SALES TRENDS (TIME SERIES)
    # --------------------------------------------------
    @strawberry.field
    @permission_required("reports.view_all_sales")
    def sales_trends(
        self,
        info,
        start_date: date,
        end_date: date,
    ) -> List[DailySalesTrendType]:
        """
        Returns daily sales trends within a date range.

        Used for:
        - line charts
        - performance analysis
        - forecasting inputs

        Permission:
        - reports.view_all_sales
        """

        receipts = (
            Receipt.objects
            .filter(created_at__date__gte=start_date)
            .filter(created_at__date__lte=end_date)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(
                total_sales=Sum("total"),
                receipts_count=Count("id"),
            )
            .order_by("day")
        )

        # Items sold per day (separate aggregation for correctness)
        items_by_day = (
            Receipt.objects
            .filter(created_at__date__gte=start_date)
            .filter(created_at__date__lte=end_date)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(
                items_sold=Sum("orders__items__quantity")
            )
        )

        items_lookup = {
            row["day"]: row["items_sold"] or 0
            for row in items_by_day
        }

        return [
            DailySalesTrendType(
                date=row["day"],
                total_sales=row["total_sales"] or 0,
                receipts_count=row["receipts_count"],
                items_sold=items_lookup.get(row["day"], 0),
            )
            for row in receipts
        ]
