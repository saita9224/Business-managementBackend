# hr/queries.py

from typing import List, Optional
import strawberry
from strawberry.types import Info
from graphql import GraphQLError
from asgiref.sync import sync_to_async

from employees.decorators import permission_required

from .models import (
    EmployeeContract,
    AttendanceRecord,
    LeaveRequest,
    SalaryRecord,
    SalaryPayment,
)
from .types import (
    EmployeeContractType,
    AttendanceRecordType,
    AttendanceSummaryType,
    LeaveRequestType,
    SalaryRecordType,
    SalaryPaymentType,
    wrap_contract,
    wrap_attendance,
    wrap_leave_request,
    wrap_salary_record,
    wrap_salary_payment,
)
from .services import _working_days_in_month
from employees.types import EmployeeType

from decimal import Decimal
import calendar
from datetime import date


@strawberry.type
class HRQuery:

    # ======================================================
    # CONTRACTS
    # ======================================================

    @strawberry.field
    @permission_required("hr.view_contracts")
    async def employee_contract(
        self,
        info: Info,
        employee_id: strawberry.ID,
    ) -> Optional[EmployeeContractType]:
        """Manager views any employee's contract."""

        def fetch():
            return EmployeeContract.objects.filter(
                employee_id=employee_id,
                is_active=True,
            ).first()

        contract = await sync_to_async(fetch)()
        if contract is None:
            return None
        return wrap_contract(contract)

    @strawberry.field
    @permission_required("hr.view_contracts")
    async def all_contracts(
        self,
        info: Info,
        active_only: bool = True,
    ) -> List[EmployeeContractType]:
        """Manager lists all employee contracts."""

        def fetch():
            qs = EmployeeContract.objects.select_related("employee")
            if active_only:
                qs = qs.filter(is_active=True)
            return list(qs.order_by("employee__name"))

        contracts = await sync_to_async(fetch)()
        return [wrap_contract(c) for c in contracts]

    @strawberry.field
    @permission_required("hr.view_contracts")
    async def my_contract(
        self,
        info: Info,
    ) -> Optional[EmployeeContractType]:
        """Employee views their own contract."""
        employee = info.context.user

        def fetch():
            return EmployeeContract.objects.filter(
                employee=employee,
                is_active=True,
            ).first()

        contract = await sync_to_async(fetch)()
        if contract is None:
            return None
        return wrap_contract(contract)

    # ======================================================
    # ATTENDANCE
    # ======================================================

    @strawberry.field
    @permission_required("hr.view_attendance")
    async def employee_attendance(
        self,
        info: Info,
        employee_id: strawberry.ID,
        year:        int,
        month:       int,
    ) -> List[AttendanceRecordType]:
        """Manager views attendance for any employee for a given month."""

        def fetch():
            _, last = calendar.monthrange(year, month)
            return list(
                AttendanceRecord.objects.filter(
                    employee_id=employee_id,
                    date__year=year,
                    date__month=month,
                ).order_by("date")
            )

        records = await sync_to_async(fetch)()
        return [wrap_attendance(r) for r in records]

    @strawberry.field
    @permission_required("hr.self_checkin")
    async def my_attendance(
        self,
        info: Info,
        year:  int,
        month: int,
    ) -> List[AttendanceRecordType]:
        """Employee views their own attendance for a given month."""
        employee = info.context.user

        def fetch():
            return list(
                AttendanceRecord.objects.filter(
                    employee=employee,
                    date__year=year,
                    date__month=month,
                ).order_by("date")
            )

        records = await sync_to_async(fetch)()
        return [wrap_attendance(r) for r in records]

    @strawberry.field
    @permission_required("hr.view_attendance")
    async def today_attendance(
        self,
        info: Info,
    ) -> List[AttendanceRecordType]:
        """Manager views all attendance records for today."""

        def fetch():
            return list(
                AttendanceRecord.objects
                .filter(date=date.today())
                .select_related("employee", "recorded_by")
                .order_by("employee__name")
            )

        records = await sync_to_async(fetch)()
        return [wrap_attendance(r) for r in records]

    @strawberry.field
    @permission_required("hr.view_attendance")
    async def attendance_summary(
        self,
        info: Info,
        employee_id: strawberry.ID,
        year:        int,
        month:       int,
    ) -> AttendanceSummaryType:
        """
        Returns a summary of attendance for an employee
        for a given month — used for payslip preview.
        """
        from employees.models import Employee

        def fetch():
            employee = Employee.objects.get(pk=employee_id)
            contract = EmployeeContract.objects.filter(
                employee=employee,
                is_active=True,
            ).first()

            _, last = calendar.monthrange(year, month)
            records = AttendanceRecord.objects.filter(
                employee=employee,
                date__year=year,
                date__month=month,
            )

            days_present  = Decimal("0")
            days_absent   = Decimal("0")
            days_late     = Decimal("0")
            days_half     = Decimal("0")

            for r in records:
                if r.status == AttendanceRecord.PRESENT:
                    days_present += Decimal("1")
                elif r.status == AttendanceRecord.ABSENT:
                    days_absent  += Decimal("1")
                elif r.status == AttendanceRecord.LATE:
                    days_late    += Decimal("1")
                elif r.status == AttendanceRecord.HALF_DAY:
                    days_half    += Decimal("1")

            # Leave days
            from .services import _get_approved_leave_days
            approved_leave_dates = _get_approved_leave_days(
                employee, year, month
            )
            attended_dates         = {r.date for r in records}
            unattended_leave_dates = [
                d for d in approved_leave_dates
                if d not in attended_dates
            ]

            leave_weight  = Decimal(
                str(contract.leave_pay_weight) if contract else "1.0"
            )
            days_on_leave = Decimal(
                str(len(unattended_leave_dates))
            ) * leave_weight

            # Effective days = weighted present + weighted leave
            effective_days = (
                days_present
                + days_late
                + (days_half * Decimal("0.5"))
                + days_on_leave
            )

            working_days = _working_days_in_month(
                year, month,
                contract.working_days_per_week if contract else 5,
            )

            return (
                employee,
                working_days,
                days_present,
                days_absent,
                days_late,
                days_half,
                days_on_leave,
                effective_days,
            )

        (
            employee,
            working_days,
            days_present,
            days_absent,
            days_late,
            days_half,
            days_on_leave,
            effective_days,
        ) = await sync_to_async(fetch)()

        return AttendanceSummaryType(
            employee=employee,
            period_year=year,
            period_month=month,
            working_days=working_days,
            days_present=days_present,
            days_absent=days_absent,
            days_late=days_late,
            days_half=days_half,
            days_on_leave=days_on_leave,
            effective_days=effective_days,
        )

    # ======================================================
    # LEAVE REQUESTS
    # ======================================================

    @strawberry.field
    @permission_required("hr.request_leave")
    async def my_leave_requests(
        self,
        info: Info,
    ) -> List[LeaveRequestType]:
        """Employee views their own leave requests."""
        employee = info.context.user

        def fetch():
            return list(
                LeaveRequest.objects.filter(employee=employee)
                .select_related("reviewed_by")
                .order_by("-created_at")
            )

        requests = await sync_to_async(fetch)()
        return [wrap_leave_request(r) for r in requests]

    @strawberry.field
    @permission_required("hr.view_leave")
    async def leave_requests(
        self,
        info: Info,
        status:      Optional[str]         = None,
        employee_id: Optional[strawberry.ID] = None,
    ) -> List[LeaveRequestType]:
        """Manager views all leave requests, optionally filtered."""

        def fetch():
            qs = LeaveRequest.objects.select_related(
                "employee", "reviewed_by"
            ).order_by("-created_at")
            if status:
                qs = qs.filter(status=status)
            if employee_id:
                qs = qs.filter(employee_id=employee_id)
            return list(qs)

        requests = await sync_to_async(fetch)()
        return [wrap_leave_request(r) for r in requests]

    # ======================================================
    # SALARY RECORDS
    # ======================================================

    @strawberry.field
    @permission_required("hr.view_salary")
    async def salary_records(
        self,
        info: Info,
        year:        Optional[int]         = None,
        month:       Optional[int]         = None,
        employee_id: Optional[strawberry.ID] = None,
        status:      Optional[str]         = None,
    ) -> List[SalaryRecordType]:
        """Manager views all payslips with optional filters."""

        def fetch():
            qs = SalaryRecord.objects.select_related(
                "employee", "approved_by"
            ).order_by("-period_year", "-period_month", "employee__name")
            if year:
                qs = qs.filter(period_year=year)
            if month:
                qs = qs.filter(period_month=month)
            if employee_id:
                qs = qs.filter(employee_id=employee_id)
            if status:
                qs = qs.filter(status=status)
            return list(qs)

        records = await sync_to_async(fetch)()
        return [wrap_salary_record(r) for r in records]

    @strawberry.field
    @permission_required("hr.view_salary")
    async def salary_record(
        self,
        info: Info,
        salary_record_id: strawberry.ID,
    ) -> SalaryRecordType:
        """Manager views a single payslip."""

        def fetch():
            try:
                return SalaryRecord.objects.select_related(
                    "employee", "approved_by"
                ).get(pk=salary_record_id)
            except SalaryRecord.DoesNotExist:
                return None

        record = await sync_to_async(fetch)()
        if record is None:
            raise GraphQLError("Salary record not found.")
        return wrap_salary_record(record)

    @strawberry.field
    @permission_required("hr.view_salary")
    async def my_payslips(
        self,
        info: Info,
        year: Optional[int] = None,
    ) -> List[SalaryRecordType]:
        """Employee views their own payslips."""
        employee = info.context.user

        def fetch():
            qs = SalaryRecord.objects.filter(
                employee=employee,
            ).order_by("-period_year", "-period_month")
            if year:
                qs = qs.filter(period_year=year)
            return list(qs)

        records = await sync_to_async(fetch)()
        return [wrap_salary_record(r) for r in records]

    @strawberry.field
    @permission_required("hr.manage_salary")
    async def salary_payments(
        self,
        info: Info,
        salary_record_id: strawberry.ID,
    ) -> List[SalaryPaymentType]:
        """Lists all payments made against a payslip."""

        def fetch():
            return list(
                SalaryPayment.objects.filter(
                    salary_record_id=salary_record_id,
                ).select_related("paid_by")
                .order_by("-paid_at")
            )

        payments = await sync_to_async(fetch)()
        return [wrap_salary_payment(p) for p in payments]