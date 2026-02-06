# reports/services/sales_trends.py

"""
Sales trends services.

Provides time-series sales data (daily / monthly) for reporting and analytics.

Design rules:
- Accept Receipt queryset
- No permission logic here
- No GraphQL imports
- Database-level aggregation
"""

from decimal import Decimal
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate, TruncMonth

from POS.models import Receipt, OrderItem


# ======================================================
# INTERNAL UTIL
# ======================================================

def _apply_date_filters(queryset, start_date=None, end_date=None):
    """
    Applies optional date filters to a Receipt queryset.
    """
    if start_date:
        queryset = queryset.filter(created_at__date__gte=start_date)
    if end_date:
        queryset = queryset.filter(created_at__date__lte=end_date)
    return queryset


# ======================================================
# DAILY SALES TRENDS
# ======================================================

def get_daily_sales_trends(receipts_queryset, start_date=None, end_date=None):
    """
    Returns daily sales trends.

    Output example:
    [
        {
            "period": date(2026, 1, 15),
            "total_sales": 45200,
            "receipts_count": 38,
            "items_sold": 112
        }
    ]
    """

    receipts_queryset = _apply_date_filters(
        receipts_queryset,
        start_date,
        end_date,
    )

    daily_receipts = (
        receipts_queryset
        .annotate(period=TruncDate("created_at"))
        .values("period")
        .annotate(
            total_sales=Sum("total"),
            receipts_count=Count("id"),
        )
        .order_by("period")
    )

    trends = []

    for row in daily_receipts:
        receipts_for_day = receipts_queryset.filter(
            created_at__date=row["period"]
        )

        items_sold = (
            OrderItem.objects
            .filter(order__receipt__in=receipts_for_day)
            .aggregate(total=Sum("quantity"))
            ["total"]
            or Decimal("0")
        )

        trends.append({
            "period": row["period"],
            "total_sales": row["total_sales"] or Decimal("0.00"),
            "receipts_count": row["receipts_count"],
            "items_sold": items_sold,
        })

    return trends


# ======================================================
# MONTHLY SALES TRENDS
# ======================================================

def get_monthly_sales_trends(receipts_queryset, start_date=None, end_date=None):
    """
    Returns monthly sales trends (calendar months).

    Output example:
    [
        {
            "period": "2026-01",
            "total_sales": 1245000,
            "receipts_count": 987,
            "items_sold": 3120
        }
    ]
    """

    receipts_queryset = _apply_date_filters(
        receipts_queryset,
        start_date,
        end_date,
    )

    monthly_receipts = (
        receipts_queryset
        .annotate(period=TruncMonth("created_at"))
        .values("period")
        .annotate(
            total_sales=Sum("total"),
            receipts_count=Count("id"),
        )
        .order_by("period")
    )

    trends = []

    for row in monthly_receipts:
        receipts_for_month = receipts_queryset.filter(
            created_at__year=row["period"].year,
            created_at__month=row["period"].month,
        )

        items_sold = (
            OrderItem.objects
            .filter(order__receipt__in=receipts_for_month)
            .aggregate(total=Sum("quantity"))
            ["total"]
            or Decimal("0")
        )

        trends.append({
            "period": row["period"].strftime("%Y-%m"),
            "total_sales": row["total_sales"] or Decimal("0.00"),
            "receipts_count": row["receipts_count"],
            "items_sold": items_sold,
        })

    return trends
