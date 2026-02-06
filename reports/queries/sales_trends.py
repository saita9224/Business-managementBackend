# reports/queries/sales_trends.py

"""
Sales trends GraphQL queries.

Exposes time-series sales data (daily / monthly) via GraphQL.

ACCESS CONTROL (RBAC):
- reports.view_all_sales → can see all sales trends
- reports.view_own_sales → can see own sales trends only

Design principles:
- Queries orchestrate only
- Services calculate
- Permissions enforced at resolver level
"""

import strawberry
from typing import Optional, List
from datetime import date

from employees.decorators import permission_required
from POS.models import Receipt

from reports.services.sales_trends import (
    get_daily_sales_trends,
    get_monthly_sales_trends,
)

# ======================================================
# GRAPHQL TYPES
# ======================================================

@strawberry.type
class SalesTrendPointType:
    """
    Represents a single point in a sales trend chart.
    """

    period: str        # date (YYYY-MM-DD) or month (YYYY-MM)
    total_sales: float
    receipts_count: int
    items_sold: float


# ======================================================
# INTERNAL MAPPERS
# ======================================================

def _map_trend_points(trends: list) -> List[SalesTrendPointType]:
    """
    Maps service-layer trend dicts into GraphQL types.
    """
    return [
        SalesTrendPointType(
            period=str(t["period"]),
            total_sales=t["total_sales"],
            receipts_count=t["receipts_count"],
            items_sold=t["items_sold"],
        )
        for t in trends
    ]


# ======================================================
# SALES TRENDS QUERIES
# ======================================================

@strawberry.type
class SalesTrendsQueries:
    """
    Sales trends reporting queries.
    """

    # --------------------------------------------------
    # 1. DAILY SALES TRENDS (ADMIN / MANAGER)
    # --------------------------------------------------
    @strawberry.field
    @permission_required("reports.view_sales_trends")
    def daily_sales_trends(
        self,
        info,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[SalesTrendPointType]:
        """
        Returns daily sales trends for the entire system.

        Permission:
        - reports.view_all_sales
        """

        receipts = Receipt.objects.all()

        trends = get_daily_sales_trends(
            receipts_queryset=receipts,
            start_date=start_date,
            end_date=end_date,
        )

        return _map_trend_points(trends)

    # --------------------------------------------------
    # 2. DAILY SALES TRENDS (OWN SALES)
    # --------------------------------------------------
    @strawberry.field
    @permission_required("reports.view_own_sales")
    def my_daily_sales_trends(
        self,
        info,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[SalesTrendPointType]:
        """
        Returns daily sales trends for the logged-in employee only.

        Permission:
        - reports.view_own_sales
        """

        user = info.context.user

        receipts = Receipt.objects.filter(created_by=user)

        trends = get_daily_sales_trends(
            receipts_queryset=receipts,
            start_date=start_date,
            end_date=end_date,
        )

        return _map_trend_points(trends)

    # --------------------------------------------------
    # 3. MONTHLY SALES TRENDS (ADMIN / MANAGER)
    # --------------------------------------------------
    @strawberry.field
    @permission_required("reports.view_sales_trends")
    def monthly_sales_trends(
        self,
        info,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[SalesTrendPointType]:
        """
        Returns monthly (calendar-based) sales trends.

        Permission:
        - reports.view_all_sales
        """

        receipts = Receipt.objects.all()

        trends = get_monthly_sales_trends(
            receipts_queryset=receipts,
            start_date=start_date,
            end_date=end_date,
        )

        return _map_trend_points(trends)

    # --------------------------------------------------
    # 4. MONTHLY SALES TRENDS (OWN SALES)
    # --------------------------------------------------
    @strawberry.field
    @permission_required("reports.view_own_sales")
    def my_monthly_sales_trends(
        self,
        info,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[SalesTrendPointType]:
        """
        Returns monthly sales trends for the logged-in employee only.

        Permission:
        - reports.view_own_sales
        """

        user = info.context.user

        receipts = Receipt.objects.filter(created_by=user)

        trends = get_monthly_sales_trends(
            receipts_queryset=receipts,
            start_date=start_date,
            end_date=end_date,
        )

        return _map_trend_points(trends)
