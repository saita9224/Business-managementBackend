# hr/types.py

from typing import List, Optional
from datetime import datetime, date, time
from decimal import Decimal

import strawberry
from strawberry.types import Info
from strawberry import Private
from graphql import GraphQLError


# ======================================================
# MINIMAL EMPLOYEE REFERENCE
# ======================================================

@strawberry.type
class HREmployeeRef:
    id:    strawberry.ID
    name:  str
    email: str
    phone: Optional[str] = None


# ======================================================
# AUTH HELPER
# ======================================================

def require_auth(info: Info):
    employee = info.context.user
    if not employee or not employee.is_authenticated:
        raise GraphQLError("Authentication required")
    return employee


# ── Internal helper ────────────────────────────────────

async def _fetch_employee_ref(employee_id: int) -> HREmployeeRef:
    from employees.models import Employee
    from asgiref.sync import sync_to_async
    emp = await sync_to_async(Employee.objects.get)(pk=employee_id)
    return HREmployeeRef(
        id=emp.id,
        name=emp.name,
        email=emp.email,
        phone=emp.phone or None,
    )


# ======================================================
# EMPLOYEE CONTRACT
# ======================================================

@strawberry.type
class EmployeeContractType:
    id:                    strawberry.ID
    department:            str
    position:              str
    employment_type:       str
    date_hired:            date
    base_monthly:          Decimal
    check_in_time:         time
    late_threshold_mins:   int
    working_days_per_week: int
    leave_pay_policy:      str
    is_active:             bool
    created_at:            datetime
    updated_at:            datetime

    _employee_id: Private[int]

    @strawberry.field
    async def employee(self, info: Info) -> HREmployeeRef:
        require_auth(info)
        return await _fetch_employee_ref(self._employee_id)

    @strawberry.field
    def leave_pay_weight(self) -> float:
        return {
            "FULL_PAY": 1.0,
            "HALF_PAY": 0.5,
            "NO_PAY":   0.0,
        }.get(self.leave_pay_policy, 1.0)


# ======================================================
# ATTENDANCE RECORD
# ======================================================

@strawberry.type
class AttendanceRecordType:
    id:          strawberry.ID
    date:        date
    time_in:     Optional[time]
    time_out:    Optional[time]
    status:      str
    source:      str
    notes:       Optional[str]
    created_at:  datetime
    updated_at:  datetime

    _employee_id:    Private[int]
    _recorded_by_id: Private[Optional[int]]

    @strawberry.field
    async def employee(self, info: Info) -> HREmployeeRef:
        require_auth(info)
        return await _fetch_employee_ref(self._employee_id)

    @strawberry.field
    async def recorded_by(self, info: Info) -> Optional[HREmployeeRef]:
        require_auth(info)
        if not self._recorded_by_id:
            return None
        return await _fetch_employee_ref(self._recorded_by_id)

    @strawberry.field
    def attendance_weight(self) -> float:
        return {
            "PRESENT":  1.0,
            "LATE":     1.0,
            "HALF_DAY": 0.5,
            "ABSENT":   0.0,
        }.get(self.status, 0.0)


# ======================================================
# LEAVE REQUEST
# ======================================================

@strawberry.type
class LeaveRequestType:
    id:           strawberry.ID
    leave_type:   str
    start_date:   date
    end_date:     date
    reason:       Optional[str]
    status:       str
    reviewed_at:  Optional[datetime]
    review_notes: Optional[str]
    created_at:   datetime

    _employee_id:    Private[int]
    _reviewed_by_id: Private[Optional[int]]

    @strawberry.field
    async def employee(self, info: Info) -> HREmployeeRef:
        require_auth(info)
        return await _fetch_employee_ref(self._employee_id)

    @strawberry.field
    async def reviewed_by(self, info: Info) -> Optional[HREmployeeRef]:
        require_auth(info)
        if not self._reviewed_by_id:
            return None
        return await _fetch_employee_ref(self._reviewed_by_id)

    @strawberry.field
    def total_days(self) -> int:
        return (self.end_date - self.start_date).days + 1


# ======================================================
# SALARY PAYMENT
# ======================================================

@strawberry.type
class SalaryPaymentType:
    id:             strawberry.ID
    amount:         Decimal
    payment_method: str
    reference:      Optional[str]
    notes:          Optional[str]
    paid_at:        datetime

    _paid_by_id:       Private[Optional[int]]
    _salary_record_id: Private[int]

    @strawberry.field
    async def paid_by(self, info: Info) -> Optional[HREmployeeRef]:
        require_auth(info)
        if not self._paid_by_id:
            return None
        return await _fetch_employee_ref(self._paid_by_id)


# ======================================================
# SALARY RECORD
# ======================================================

@strawberry.type
class SalaryRecordType:
    id:            strawberry.ID
    period_year:   int
    period_month:  int
    base_monthly:  Decimal
    working_days:  int
    days_present:  Decimal
    days_on_leave: Decimal
    gross_amount:  Decimal
    deductions:    Decimal
    net_amount:    Decimal
    total_paid:    Decimal
    balance:       Decimal
    status:        str
    approved_at:   Optional[datetime]
    created_at:    datetime

    _employee_id:    Private[int]
    _approved_by_id: Private[Optional[int]]

    @strawberry.field
    async def employee(self, info: Info) -> HREmployeeRef:
        require_auth(info)
        return await _fetch_employee_ref(self._employee_id)

    @strawberry.field
    async def approved_by(self, info: Info) -> Optional[HREmployeeRef]:
        require_auth(info)
        if not self._approved_by_id:
            return None
        return await _fetch_employee_ref(self._approved_by_id)

    @strawberry.field
    def is_fully_paid(self) -> bool:
        return self.balance <= 0

    @strawberry.field
    def period_label(self) -> str:
        return date(self.period_year, self.period_month, 1).strftime("%B %Y")

    @strawberry.field
    async def payments(self, info: Info) -> List[SalaryPaymentType]:
        require_auth(info)
        return await info.context.payments_by_salary_record.load(int(self.id))


# ======================================================
# ATTENDANCE SUMMARY
# ======================================================

@strawberry.type
class AttendanceSummaryType:
    employee:       HREmployeeRef
    period_year:    int
    period_month:   int
    working_days:   int
    days_present:   Decimal
    days_absent:    Decimal
    days_late:      Decimal
    days_half:      Decimal
    days_on_leave:  Decimal
    effective_days: Decimal


# ======================================================
# WRAP HELPERS
# ======================================================

def wrap_contract(contract) -> EmployeeContractType:
    return EmployeeContractType(
        id=contract.id,
        department=contract.department,
        position=contract.position,
        employment_type=contract.employment_type,
        date_hired=contract.date_hired,
        base_monthly=contract.base_monthly,
        check_in_time=contract.check_in_time,
        late_threshold_mins=contract.late_threshold_mins,
        working_days_per_week=contract.working_days_per_week,
        leave_pay_policy=contract.leave_pay_policy,
        is_active=contract.is_active,
        created_at=contract.created_at,
        updated_at=contract.updated_at,
        _employee_id=contract.employee_id,
    )


def wrap_attendance(record) -> AttendanceRecordType:
    return AttendanceRecordType(
        id=record.id,
        date=record.date,
        time_in=record.time_in,
        time_out=record.time_out,
        status=record.status,
        source=record.source,
        notes=record.notes,
        created_at=record.created_at,
        updated_at=record.updated_at,
        _employee_id=record.employee_id,
        _recorded_by_id=record.recorded_by_id,
    )


def wrap_leave_request(leave) -> LeaveRequestType:
    return LeaveRequestType(
        id=leave.id,
        leave_type=leave.leave_type,
        start_date=leave.start_date,
        end_date=leave.end_date,
        reason=leave.reason,
        status=leave.status,
        reviewed_at=leave.reviewed_at,
        review_notes=leave.review_notes,
        created_at=leave.created_at,
        _employee_id=leave.employee_id,
        _reviewed_by_id=leave.reviewed_by_id,
    )


def wrap_salary_record(record) -> SalaryRecordType:
    return SalaryRecordType(
        id=record.id,
        period_year=record.period_year,
        period_month=record.period_month,
        base_monthly=record.base_monthly,
        working_days=record.working_days,
        days_present=record.days_present,
        days_on_leave=record.days_on_leave,
        gross_amount=record.gross_amount,
        deductions=record.deductions,
        net_amount=record.net_amount,
        total_paid=record.total_paid,
        balance=record.balance,
        status=record.status,
        approved_at=record.approved_at,
        created_at=record.created_at,
        _employee_id=record.employee_id,
        _approved_by_id=record.approved_by_id,
    )


def wrap_salary_payment(payment) -> SalaryPaymentType:
    return SalaryPaymentType(
        id=payment.id,
        amount=payment.amount,
        payment_method=payment.payment_method,
        reference=payment.reference,
        notes=payment.notes,
        paid_at=payment.paid_at,
        _paid_by_id=payment.paid_by_id,
        _salary_record_id=payment.salary_record_id,
    )