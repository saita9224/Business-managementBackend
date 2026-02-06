# reports/types.py
import strawberry
from decimal import Decimal
from typing import Optional


@strawberry.type
class PaymentBreakdownType:
    method: str
    amount: Decimal


@strawberry.type
class SalesSummaryType:
    total_sales: Decimal
    receipts_count: int
    items_sold: Decimal
    payments: list[PaymentBreakdownType]
