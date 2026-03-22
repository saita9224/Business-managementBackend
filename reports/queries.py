# reports/queries.py

from datetime import date, timedelta
from decimal import Decimal
from typing import List

import strawberry
from strawberry.types import Info
from asgiref.sync import sync_to_async
from django.db.models import (
    Sum, Count, Q, F,
    DecimalField,
)
from django.db.models.functions import TruncDate, Coalesce
from django.utils import timezone

from employees.decorators import permission_required

from .types import (
    SalesSummaryType,
    SalesDailyBreakdownType,
    PaymentMethodBreakdownType,
    ProductPerformanceItemType,
    ExpenseSummaryType,
    ExpenseDailyBreakdownType,
    ExpenseSupplierBreakdownType,
    StockHealthItemType,
    PayrollSummaryType,
    PayrollEmployeeSummaryType,
    AttendanceReportType,
    AttendanceEmployeeReportType,
    CreditExposureSummaryType,
    CreditExposureItemType,
)

ZERO = Decimal("0.00")


def _dec(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


@strawberry.type
class ReportQuery:

    # ======================================================
    # SALES REPORT
    # ======================================================

    @strawberry.field
    @permission_required("reports.view_sales")
    async def sales_report(
        self,
        info:       Info,
        start_date: date,
        end_date:   date,
    ) -> SalesSummaryType:

        def fetch():
            from POS.models import Receipt, Payment

            paid_statuses = [Receipt.PAID, Receipt.CREDIT]

            revenue_qs = Receipt.objects.filter(
                status__in=paid_statuses,
                submitted_at__date__gte=start_date,
                submitted_at__date__lte=end_date,
            )

            revenue_agg = revenue_qs.aggregate(
                total_revenue=Coalesce(
                    Sum("total"), ZERO,
                    output_field=DecimalField()
                ),
                order_count=Count("id"),
            )

            total_revenue   = _dec(revenue_agg["total_revenue"])
            order_count     = revenue_agg["order_count"] or 0
            avg_order_value = (
                _dec(total_revenue / order_count)
                if order_count > 0 else ZERO
            )

            credit_agg = Receipt.objects.filter(
                status=Receipt.CREDIT,
                submitted_at__date__gte=start_date,
                submitted_at__date__lte=end_date,
            ).aggregate(
                total=Coalesce(Sum("total"), ZERO, output_field=DecimalField())
            )
            credit_total = _dec(credit_agg["total"])

            refund_agg = Receipt.objects.filter(
                status=Receipt.REFUNDED,
                refunded_at__date__gte=start_date,
                refunded_at__date__lte=end_date,
            ).aggregate(
                total=Coalesce(Sum("total"), ZERO, output_field=DecimalField())
            )
            refund_total = _dec(refund_agg["total"])
            net_revenue  = _dec(total_revenue - refund_total)

            payment_rows = (
                Payment.objects
                .filter(
                    receipt__status__in=paid_statuses,
                    created_at__date__gte=start_date,
                    created_at__date__lte=end_date,
                )
                .values("method")
                .annotate(
                    total=Coalesce(Sum("amount"), ZERO, output_field=DecimalField()),
                    count=Count("id"),
                )
                .order_by("-total")
            )

            payment_breakdown = [
                PaymentMethodBreakdownType(
                    method=row["method"],
                    total=_dec(row["total"]),
                    count=row["count"],
                )
                for row in payment_rows
            ]

            daily_rows = (
                revenue_qs
                .annotate(day=TruncDate("submitted_at"))
                .values("day")
                .annotate(
                    revenue=Coalesce(Sum("total"), ZERO, output_field=DecimalField()),
                    order_count=Count("id"),
                )
                .order_by("day")
            )

            daily_breakdown = [
                SalesDailyBreakdownType(
                    date=row["day"],
                    revenue=_dec(row["revenue"]),
                    order_count=row["order_count"],
                    avg_order_value=_dec(
                        row["revenue"] / row["order_count"]
                        if row["order_count"] > 0 else 0
                    ),
                )
                for row in daily_rows
            ]

            return SalesSummaryType(
                total_revenue=total_revenue,
                order_count=order_count,
                avg_order_value=avg_order_value,
                refund_total=refund_total,
                credit_total=credit_total,
                net_revenue=net_revenue,
                payment_breakdown=payment_breakdown,
                daily_breakdown=daily_breakdown,
            )

        return await sync_to_async(fetch)()


    # ======================================================
    # PRODUCT PERFORMANCE REPORT
    # ======================================================

    @strawberry.field
    @permission_required("reports.view_sales")
    async def product_performance_report(
        self,
        info:       Info,
        start_date: date,
        end_date:   date,
        limit:      int = 20,
    ) -> List[ProductPerformanceItemType]:

        def fetch():
            from POS.models import OrderItem, Receipt

            rows = (
                OrderItem.objects
                .filter(
                    order__receipt__status__in=[Receipt.PAID, Receipt.CREDIT],
                    order__receipt__submitted_at__date__gte=start_date,
                    order__receipt__submitted_at__date__lte=end_date,
                )
                .exclude(product_id=0)
                .values("product_id", "product_name")
                .annotate(
                    units_sold=Coalesce(
                        Sum("quantity"), ZERO,
                        output_field=DecimalField()
                    ),
                    revenue=Coalesce(
                        Sum("line_total"), ZERO,
                        output_field=DecimalField()
                    ),
                    order_count=Count("order__receipt", distinct=True),
                )
                .order_by("-revenue", "-units_sold")
                [:limit]
            )

            return [
                ProductPerformanceItemType(
                    product_id=str(row["product_id"]),
                    product_name=row["product_name"],
                    units_sold=_dec(row["units_sold"]),
                    revenue=_dec(row["revenue"]),
                    order_count=row["order_count"],
                )
                for row in rows
            ]

        return await sync_to_async(fetch)()


    # ======================================================
    # EXPENSE REPORT
    # ======================================================

    @strawberry.field
    @permission_required("reports.view_expenses")
    async def expense_report(
        self,
        info:       Info,
        start_date: date,
        end_date:   date,
    ) -> ExpenseSummaryType:

        def fetch():
            from expenses.models import ExpenseItem, ExpensePayment

            expense_qs = ExpenseItem.objects.filter(
                created_at__date__gte=start_date,
                created_at__date__lte=end_date,
            )

            total_agg = expense_qs.aggregate(
                total_expenses=Coalesce(
                    Sum("total_price"), ZERO,
                    output_field=DecimalField()
                ),
            )
            total_expenses = _dec(total_agg["total_expenses"])

            paid_agg = ExpensePayment.objects.filter(
                expense__created_at__date__gte=start_date,
                expense__created_at__date__lte=end_date,
            ).aggregate(
                total_paid=Coalesce(
                    Sum("amount"), ZERO,
                    output_field=DecimalField()
                ),
            )
            total_paid        = _dec(paid_agg["total_paid"])
            total_outstanding = _dec(total_expenses - total_paid)

            daily_rows = (
                expense_qs
                .annotate(day=TruncDate("created_at"))
                .values("day")
                .annotate(
                    total_spent=Coalesce(
                        Sum("total_price"), ZERO,
                        output_field=DecimalField()
                    ),
                    item_count=Count("id"),
                )
                .order_by("day")
            )

            daily_breakdown = [
                ExpenseDailyBreakdownType(
                    date=row["day"],
                    total_spent=_dec(row["total_spent"]),
                    item_count=row["item_count"],
                )
                for row in daily_rows
            ]

            supplier_rows = (
                expense_qs
                .values(supplier_name=F("supplier__name"))
                .annotate(
                    total_spent=Coalesce(
                        Sum("total_price"), ZERO,
                        output_field=DecimalField()
                    ),
                    item_count=Count("id"),
                )
                .order_by("-total_spent")
            )

            supplier_breakdown = [
                ExpenseSupplierBreakdownType(
                    supplier_name=row["supplier_name"] or "No Supplier",
                    total_spent=_dec(row["total_spent"]),
                    item_count=row["item_count"],
                )
                for row in supplier_rows
            ]

            return ExpenseSummaryType(
                total_expenses=total_expenses,
                total_paid=total_paid,
                total_outstanding=total_outstanding,
                daily_breakdown=daily_breakdown,
                supplier_breakdown=supplier_breakdown,
            )

        return await sync_to_async(fetch)()


    # ======================================================
    # STOCK HEALTH REPORT
    # ======================================================

    @strawberry.field
    @permission_required("reports.view_inventory")
    async def stock_health_report(
        self,
        info:       Info,
        start_date: date,
        end_date:   date,
    ) -> List[StockHealthItemType]:

        def fetch():
            from inventory.models import Product, StockMovement

            products = list(Product.objects.all().order_by("name"))

            all_time_movements = (
                StockMovement.objects
                .values("product_id")
                .annotate(
                    total_in=Coalesce(
                        Sum("quantity", filter=Q(movement_type=StockMovement.IN)),
                        ZERO, output_field=DecimalField()
                    ),
                    total_out=Coalesce(
                        Sum("quantity", filter=Q(movement_type=StockMovement.OUT)),
                        ZERO, output_field=DecimalField()
                    ),
                )
            )
            stock_map = {
                row["product_id"]: _dec(row["total_in"]) - _dec(row["total_out"])
                for row in all_time_movements
            }

            period_movements = (
                StockMovement.objects
                .filter(
                    created_at__date__gte=start_date,
                    created_at__date__lte=end_date,
                )
                .values("product_id")
                .annotate(
                    period_in=Coalesce(
                        Sum("quantity", filter=Q(movement_type=StockMovement.IN)),
                        ZERO, output_field=DecimalField()
                    ),
                    period_out=Coalesce(
                        Sum("quantity", filter=Q(movement_type=StockMovement.OUT)),
                        ZERO, output_field=DecimalField()
                    ),
                    period_adj=Coalesce(
                        Sum(
                            "quantity",
                            filter=Q(reason=StockMovement.ADJUSTMENT),
                        ),
                        ZERO, output_field=DecimalField()
                    ),
                )
            )
            period_map = {
                row["product_id"]: row
                for row in period_movements
            }

            result = []
            for product in products:
                current_stock = stock_map.get(product.id, ZERO)
                period        = period_map.get(product.id, {})

                if current_stock <= 0:
                    status = "OUT"
                elif current_stock < 10:
                    status = "LOW"
                else:
                    status = "OK"

                result.append(
                    StockHealthItemType(
                        product_id=str(product.id),
                        product_name=product.name,
                        unit=product.unit,
                        current_stock=current_stock,
                        status=status,
                        total_in=_dec(period.get("period_in", 0)),
                        total_out=_dec(period.get("period_out", 0)),
                        total_adjustments=_dec(period.get("period_adj", 0)),
                    )
                )

            return result

        return await sync_to_async(fetch)()


    # ======================================================
    # PAYROLL REPORT
    # ======================================================

    @strawberry.field
    @permission_required("reports.view_payroll")
    async def payroll_report(
        self,
        info:  Info,
        year:  int,
        month: int,
    ) -> PayrollSummaryType:

        def fetch():
            from hr.models import SalaryRecord

            records = list(
                SalaryRecord.objects
                .filter(period_year=year, period_month=month)
                .select_related("employee")
                .order_by("employee__name")
            )

            total_gross       = ZERO
            total_net         = ZERO
            total_paid        = ZERO
            total_outstanding = ZERO
            per_employee      = []

            for r in records:
                total_gross       += _dec(r.gross_amount)
                total_net         += _dec(r.net_amount)
                total_paid        += _dec(r.total_paid)
                total_outstanding += _dec(r.balance)

                per_employee.append(
                    PayrollEmployeeSummaryType(
                        employee_id=str(r.employee_id),
                        employee_name=r.employee.name,
                        gross_amount=_dec(r.gross_amount),
                        net_amount=_dec(r.net_amount),
                        total_paid=_dec(r.total_paid),
                        balance=_dec(r.balance),
                        status=r.status,
                    )
                )

            return PayrollSummaryType(
                total_gross=total_gross,
                total_net=total_net,
                total_paid=total_paid,
                total_outstanding=total_outstanding,
                per_employee=per_employee,
            )

        return await sync_to_async(fetch)()


    # ======================================================
    # ATTENDANCE REPORT
    # Renamed to AttendanceReportType to avoid collision
    # with hr/types.py AttendanceSummaryType.
    # ======================================================

    @strawberry.field
    @permission_required("reports.view_attendance")
    async def attendance_report(
        self,
        info:  Info,
        year:  int,
        month: int,
    ) -> AttendanceReportType:

        def fetch():
            from hr.models import (
                AttendanceRecord,
                EmployeeContract,
                LeaveRequest,
            )
            from hr.services import _working_days_in_month
            from employees.models import Employee
            from collections import defaultdict
            from datetime import date as date_cls
            import calendar

            _, total_days = calendar.monthrange(year, month)
            month_start   = date_cls(year, month, 1)
            month_end     = date_cls(year, month, total_days)

            employees = list(
                Employee.objects.filter(is_active=True).order_by("name")
            )

            records = list(
                AttendanceRecord.objects.filter(
                    date__year=year,
                    date__month=month,
                )
            )

            emp_records = defaultdict(list)
            for r in records:
                emp_records[r.employee_id].append(r)

            contracts = {
                c.employee_id: c
                for c in EmployeeContract.objects.filter(
                    employee__in=employees,
                    is_active=True,
                )
            }

            approved_leaves = list(
                LeaveRequest.objects.filter(
                    status=LeaveRequest.APPROVED,
                    start_date__lte=month_end,
                    end_date__gte=month_start,
                )
            )

            leave_map = defaultdict(int)
            for leave in approved_leaves:
                start = max(leave.start_date, month_start)
                end   = min(leave.end_date, month_end)
                leave_map[leave.employee_id] += (end - start).days + 1

            per_employee = []
            for emp in employees:
                emp_recs = emp_records[emp.id]
                contract = contracts.get(emp.id)

                present  = sum(1 for r in emp_recs if r.status == AttendanceRecord.PRESENT)
                absent   = sum(1 for r in emp_recs if r.status == AttendanceRecord.ABSENT)
                late     = sum(1 for r in emp_recs if r.status == AttendanceRecord.LATE)
                half_day = sum(1 for r in emp_recs if r.status == AttendanceRecord.HALF_DAY)
                on_leave = leave_map[emp.id]

                working_days = _working_days_in_month(
                    year, month,
                    contract.working_days_per_week if contract else 5,
                )

                per_employee.append(
                    AttendanceEmployeeReportType(
                        employee_id=str(emp.id),
                        employee_name=emp.name,
                        present=present,
                        absent=absent,
                        late=late,
                        half_day=half_day,
                        on_leave=on_leave,
                        total_working_days=working_days,
                    )
                )

            return AttendanceReportType(
                year=year,
                month=month,
                per_employee=per_employee,
            )

        return await sync_to_async(fetch)()


    # ======================================================
    # CREDIT EXPOSURE REPORT
    # ======================================================

    @strawberry.field
    @permission_required("reports.view_credits")
    async def credit_exposure_report(
        self,
        info: Info,
    ) -> CreditExposureSummaryType:

        def fetch():
            from POS.models import CreditAccount

            today    = timezone.now().date()
            accounts = list(
                CreditAccount.objects
                .filter(is_settled=False)
                .select_related("receipt")
                .order_by("due_date")
            )

            total_credit   = ZERO
            overdue_amount = ZERO
            overdue_count  = 0
            items          = []

            for acc in accounts:
                is_overdue    = acc.due_date < today
                total_credit += _dec(acc.credit_amount)

                if is_overdue:
                    overdue_count  += 1
                    overdue_amount += _dec(acc.credit_amount)

                items.append(
                    CreditExposureItemType(
                        receipt_number=acc.receipt.receipt_number,
                        customer_name=acc.customer_name,
                        customer_phone=acc.customer_phone or None,
                        credit_amount=_dec(acc.credit_amount),
                        due_date=acc.due_date,
                        is_overdue=is_overdue,
                    )
                )

            return CreditExposureSummaryType(
                total_credit=total_credit,
                overdue_count=overdue_count,
                overdue_amount=overdue_amount,
                accounts=items,
            )

        return await sync_to_async(fetch)()