# reports/types.py

from typing import List, Optional
from datetime import date
from decimal import Decimal

import strawberry


# ======================================================
# SALES REPORT
# ======================================================

@strawberry.type
class PaymentMethodBreakdownType:
    method: str
    total:  Decimal
    count:  int


@strawberry.type
class SalesDailyBreakdownType:
    date:            date
    revenue:         Decimal
    order_count:     int
    avg_order_value: Decimal


@strawberry.type
class SalesSummaryType:
    total_revenue:     Decimal
    order_count:       int
    avg_order_value:   Decimal
    refund_total:      Decimal
    credit_total:      Decimal
    net_revenue:       Decimal
    payment_breakdown: List[PaymentMethodBreakdownType]
    daily_breakdown:   List[SalesDailyBreakdownType]


# ======================================================
# PRODUCT PERFORMANCE REPORT
# ======================================================

@strawberry.type
class ProductPerformanceItemType:
    product_id:   strawberry.ID
    product_name: str
    units_sold:   Decimal
    revenue:      Decimal
    order_count:  int


# ======================================================
# EXPENSE REPORT
# ======================================================

@strawberry.type
class ExpenseDailyBreakdownType:
    date:        date
    total_spent: Decimal
    item_count:  int


@strawberry.type
class ExpenseSupplierBreakdownType:
    supplier_name: str
    total_spent:   Decimal
    item_count:    int


@strawberry.type
class ExpenseSummaryType:
    total_expenses:     Decimal
    total_paid:         Decimal
    total_outstanding:  Decimal
    daily_breakdown:    List[ExpenseDailyBreakdownType]
    supplier_breakdown: List[ExpenseSupplierBreakdownType]


# ======================================================
# STOCK HEALTH REPORT
# ======================================================

@strawberry.type
class StockHealthItemType:
    product_id:        strawberry.ID
    product_name:      str
    unit:              str
    current_stock:     Decimal
    status:            str
    total_in:          Decimal
    total_out:         Decimal
    total_adjustments: Decimal


# ======================================================
# PAYROLL REPORT
# ======================================================

@strawberry.type
class PayrollEmployeeSummaryType:
    employee_id:   strawberry.ID
    employee_name: str
    gross_amount:  Decimal
    net_amount:    Decimal
    total_paid:    Decimal
    balance:       Decimal
    status:        str


@strawberry.type
class PayrollSummaryType:
    total_gross:       Decimal
    total_net:         Decimal
    total_paid:        Decimal
    total_outstanding: Decimal
    per_employee:      List[PayrollEmployeeSummaryType]


# ======================================================
# ATTENDANCE REPORT
# Renamed from AttendanceSummaryType to avoid collision
# with hr/types.py which defines AttendanceSummaryType.
# ======================================================

@strawberry.type
class AttendanceEmployeeReportType:
    employee_id:        strawberry.ID
    employee_name:      str
    present:            int
    absent:             int
    late:               int
    half_day:           int
    on_leave:           int
    total_working_days: int


@strawberry.type
class AttendanceReportType:
    year:         int
    month:        int
    per_employee: List[AttendanceEmployeeReportType]


# ======================================================
# CREDIT EXPOSURE REPORT
# ======================================================

@strawberry.type
class CreditExposureItemType:
    receipt_number: str
    customer_name:  str
    customer_phone: Optional[str]
    credit_amount:  Decimal
    due_date:       date
    is_overdue:     bool


@strawberry.type
class CreditExposureSummaryType:
    total_credit:   Decimal
    overdue_count:  int
    overdue_amount: Decimal
    accounts:       List[CreditExposureItemType]