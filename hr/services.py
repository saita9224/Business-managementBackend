# hr/services.py

import calendar
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Sum, Q
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    EmployeeContract,
    AttendanceRecord,
    LeaveRequest,
    SalaryRecord,
    SalaryPayment,
)

TWO = Decimal("0.01")


# ======================================================
# INTERNAL HELPERS
# ======================================================

def _get_contract(employee) -> EmployeeContract:
    try:
        return EmployeeContract.objects.get(employee=employee, is_active=True)
    except EmployeeContract.DoesNotExist:
        raise ValidationError(
            f"No active contract found for {employee.name}. "
            "Create a contract before recording attendance or generating payslips."
        )


def _is_late(time_in: time, contract: EmployeeContract) -> bool:
    """
    Returns True if time_in exceeds check_in_time + late_threshold_mins.
    """
    cutoff = datetime.combine(date.today(), contract.check_in_time)
    cutoff += timedelta(minutes=contract.late_threshold_mins)
    actual = datetime.combine(date.today(), time_in)
    return actual > cutoff


def _working_days_in_month(year: int, month: int, days_per_week: int) -> int:
    """
    Counts working days in a month based on days_per_week.
    5 → Mon–Fri, 6 → Mon–Sat.
    """
    _, total_days = calendar.monthrange(year, month)
    weekday_limit = days_per_week - 1  # 0=Mon ... 4=Fri, 5=Sat

    count = 0
    for day in range(1, total_days + 1):
        weekday = date(year, month, day).weekday()
        if weekday <= weekday_limit:
            count += 1
    return count


def _get_approved_leave_days(
    employee,
    year: int,
    month: int,
) -> list[date]:
    """
    Returns a list of dates in the given month covered by
    approved leave requests for this employee.
    """
    month_start = date(year, month, 1)
    _, last = calendar.monthrange(year, month)
    month_end = date(year, month, last)

    approved_leaves = LeaveRequest.objects.filter(
        employee=employee,
        status=LeaveRequest.APPROVED,
        start_date__lte=month_end,
        end_date__gte=month_start,
    )

    leave_dates = []
    for leave in approved_leaves:
        current = max(leave.start_date, month_start)
        end     = min(leave.end_date, month_end)
        while current <= end:
            leave_dates.append(current)
            current += timedelta(days=1)

    return leave_dates


def _round(value) -> Decimal:
    return Decimal(str(value)).quantize(TWO, rounding=ROUND_HALF_UP)


# ======================================================
# CONTRACT SERVICES
# ======================================================

@transaction.atomic
def create_contract(
    *,
    employee,
    department:            str,
    position:              str,
    employment_type:       str,
    date_hired:            date,
    base_monthly:          Decimal | float,
    check_in_time:         time,
    late_threshold_mins:   int   = 15,
    working_days_per_week: int   = 5,
    leave_pay_policy:      str   = EmployeeContract.FULL_PAY,
) -> EmployeeContract:

    if EmployeeContract.objects.filter(
        employee=employee, is_active=True
    ).exists():
        raise ValidationError(
            f"{employee.name} already has an active contract. "
            "Deactivate it before creating a new one."
        )

    if employment_type not in dict(EmployeeContract.EMPLOYMENT_TYPES):
        raise ValidationError(f"Invalid employment type: {employment_type}")

    if leave_pay_policy not in dict(EmployeeContract.LEAVE_PAY_POLICIES):
        raise ValidationError(f"Invalid leave pay policy: {leave_pay_policy}")

    if working_days_per_week not in range(1, 8):
        raise ValidationError("working_days_per_week must be between 1 and 7.")

    contract = EmployeeContract.objects.create(
        employee=employee,
        department=department,
        position=position,
        employment_type=employment_type,
        date_hired=date_hired,
        base_monthly=_round(base_monthly),
        check_in_time=check_in_time,
        late_threshold_mins=late_threshold_mins,
        working_days_per_week=working_days_per_week,
        leave_pay_policy=leave_pay_policy,
        is_active=True,
    )
    return contract


@transaction.atomic
def update_contract(
    *,
    contract:              EmployeeContract,
    department:            str | None          = None,
    position:              str | None          = None,
    employment_type:       str | None          = None,
    base_monthly:          Decimal | float | None = None,
    check_in_time:         time | None         = None,
    late_threshold_mins:   int | None          = None,
    working_days_per_week: int | None          = None,
    leave_pay_policy:      str | None          = None,
    is_active:             bool | None         = None,
) -> EmployeeContract:

    if department            is not None: contract.department            = department
    if position              is not None: contract.position              = position
    if employment_type       is not None: contract.employment_type       = employment_type
    if base_monthly          is not None: contract.base_monthly          = _round(base_monthly)
    if check_in_time         is not None: contract.check_in_time         = check_in_time
    if late_threshold_mins   is not None: contract.late_threshold_mins   = late_threshold_mins
    if working_days_per_week is not None: contract.working_days_per_week = working_days_per_week
    if leave_pay_policy      is not None: contract.leave_pay_policy      = leave_pay_policy
    if is_active             is not None: contract.is_active             = is_active

    contract.save()
    return contract


# ======================================================
# ATTENDANCE SERVICES
# ======================================================

@transaction.atomic
def self_check_in(
    *,
    employee,
) -> AttendanceRecord:
    """
    Employee checks themselves in.
    Creates today's record or raises if already checked in.
    Status is auto-determined from contract check_in_time.
    """
    contract  = _get_contract(employee)
    today     = date.today()
    now_time  = timezone.localtime().time()

    if AttendanceRecord.objects.filter(
        employee=employee, date=today
    ).exists():
        raise ValidationError(
            "You have already checked in today."
        )

    status = (
        AttendanceRecord.LATE
        if _is_late(now_time, contract)
        else AttendanceRecord.PRESENT
    )

    return AttendanceRecord.objects.create(
        employee=employee,
        date=today,
        time_in=now_time,
        status=status,
        source=AttendanceRecord.SELF,
        recorded_by=None,
    )


@transaction.atomic
def self_check_out(
    *,
    employee,
) -> AttendanceRecord:
    """
    Employee checks themselves out.
    Must have checked in first.
    """
    today = date.today()

    try:
        record = AttendanceRecord.objects.get(
            employee=employee, date=today
        )
    except AttendanceRecord.DoesNotExist:
        raise ValidationError(
            "No check-in record found for today. Check in first."
        )

    if record.time_out is not None:
        raise ValidationError("You have already checked out today.")

    record.time_out = timezone.localtime().time()
    record.save(update_fields=["time_out", "updated_at"])
    return record


@transaction.atomic
def record_attendance(
    *,
    employee,
    recorded_by,
    attendance_date: date,
    status:          str,
    time_in:         time | None = None,
    time_out:        time | None = None,
    notes:           str | None  = None,
) -> AttendanceRecord:
    """
    Manager records attendance for any employee.
    Creates or updates the record for the given date.
    """
    if status not in dict(AttendanceRecord.STATUSES):
        raise ValidationError(f"Invalid status: {status}")

    if status != AttendanceRecord.ABSENT and time_in is None:
        raise ValidationError(
            "time_in is required for non-absent records."
        )

    record, created = AttendanceRecord.objects.update_or_create(
        employee=employee,
        date=attendance_date,
        defaults={
            "time_in":     time_in,
            "time_out":    time_out,
            "status":      status,
            "source":      AttendanceRecord.MANAGER,
            "notes":       notes,
            "recorded_by": recorded_by,
        },
    )
    return record


@transaction.atomic
def manager_check_out(
    *,
    employee,
    recorded_by,
    attendance_date: date,
    time_out:        time,
) -> AttendanceRecord:
    """
    Manager records checkout time for an employee.
    """
    try:
        record = AttendanceRecord.objects.get(
            employee=employee,
            date=attendance_date,
        )
    except AttendanceRecord.DoesNotExist:
        raise ValidationError(
            f"No attendance record found for {employee.name} on {attendance_date}."
        )

    record.time_out    = time_out
    record.recorded_by = recorded_by
    record.save(update_fields=["time_out", "recorded_by", "updated_at"])
    return record


# ======================================================
# LEAVE SERVICES
# ======================================================

@transaction.atomic
def request_leave(
    *,
    employee,
    leave_type:  str,
    start_date:  date,
    end_date:    date,
    reason:      str | None = None,
) -> LeaveRequest:

    if leave_type not in dict(LeaveRequest.LEAVE_TYPES):
        raise ValidationError(f"Invalid leave type: {leave_type}")

    if end_date < start_date:
        raise ValidationError("End date cannot be before start date.")

    # Prevent overlapping leave requests
    overlapping = LeaveRequest.objects.filter(
        employee=employee,
        status__in=[LeaveRequest.PENDING, LeaveRequest.APPROVED],
        start_date__lte=end_date,
        end_date__gte=start_date,
    ).exists()

    if overlapping:
        raise ValidationError(
            "An overlapping leave request already exists for this period."
        )

    return LeaveRequest.objects.create(
        employee=employee,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
        status=LeaveRequest.PENDING,
    )


@transaction.atomic
def review_leave(
    *,
    leave_request: LeaveRequest,
    reviewed_by,
    status:        str,
    review_notes:  str | None = None,
) -> LeaveRequest:

    if leave_request.status != LeaveRequest.PENDING:
        raise ValidationError(
            "Only pending leave requests can be reviewed."
        )

    if status not in {LeaveRequest.APPROVED, LeaveRequest.REJECTED}:
        raise ValidationError(
            f"Invalid review status: {status}. Must be APPROVED or REJECTED."
        )

    leave_request.status       = status
    leave_request.reviewed_by  = reviewed_by
    leave_request.reviewed_at  = timezone.now()
    leave_request.review_notes = review_notes
    leave_request.save(update_fields=[
        "status", "reviewed_by", "reviewed_at", "review_notes",
    ])
    return leave_request


# ======================================================
# SALARY SERVICES
# ======================================================

@transaction.atomic
def generate_payslip(
    *,
    employee,
    year:       int,
    month:      int,
    deductions: Decimal | float = 0,
    generated_by,
) -> SalaryRecord:
    """
    Generates a DRAFT payslip for an employee for a given month.

    Calculation:
    1. Get contract for base_monthly and working rules
    2. Count expected working days in month
    3. Sum weighted attendance days (PRESENT=1, LATE=1, HALF_DAY=0.5)
    4. Sum approved leave days weighted by contract leave_pay_policy
    5. gross = (days_present + days_on_leave) / working_days * base_monthly
    6. net   = gross - deductions
    7. balance = net (no payments yet)
    """

    if not 1 <= month <= 12:
        raise ValidationError("Month must be between 1 and 12.")

    if SalaryRecord.objects.filter(
        employee=employee,
        period_year=year,
        period_month=month,
    ).exists():
        raise ValidationError(
            f"A payslip for {employee.name} for "
            f"{year}/{month:02d} already exists."
        )

    contract = _get_contract(employee)

    # ── Working days ──────────────────────────────────
    working_days = _working_days_in_month(
        year, month, contract.working_days_per_week
    )

    if working_days == 0:
        raise ValidationError(
            "No working days found for this period."
        )

    # ── Attendance days (weighted) ────────────────────
    month_start = date(year, month, 1)
    _, last     = calendar.monthrange(year, month)
    month_end   = date(year, month, last)

    attendance_records = AttendanceRecord.objects.filter(
        employee=employee,
        date__gte=month_start,
        date__lte=month_end,
    )

    days_present = Decimal("0")
    for record in attendance_records:
        days_present += Decimal(str(record.attendance_weight))

    # ── Leave days (weighted by policy) ──────────────
    leave_weight    = Decimal(str(contract.leave_pay_weight))
    approved_leaves = _get_approved_leave_days(employee, year, month)

    # Exclude leave dates already counted in attendance
    attended_dates = {r.date for r in attendance_records}
    unattended_leave_dates = [
        d for d in approved_leaves if d not in attended_dates
    ]
    days_on_leave = Decimal(str(len(unattended_leave_dates))) * leave_weight

    # ── Gross calculation ─────────────────────────────
    effective_days = days_present + days_on_leave
    base           = Decimal(str(contract.base_monthly))
    gross          = (effective_days / Decimal(str(working_days))) * base
    gross          = _round(gross)

    deductions = _round(deductions)
    net        = _round(gross - deductions)
    balance    = net  # no payments yet

    return SalaryRecord.objects.create(
        employee=employee,
        period_year=year,
        period_month=month,
        base_monthly=base,
        working_days=working_days,
        days_present=days_present,
        days_on_leave=days_on_leave,
        gross_amount=gross,
        deductions=deductions,
        net_amount=net,
        total_paid=Decimal("0"),
        balance=balance,
        status=SalaryRecord.DRAFT,
    )


@transaction.atomic
def approve_payslip(
    *,
    salary_record: SalaryRecord,
    approved_by,
) -> SalaryRecord:

    if salary_record.status != SalaryRecord.DRAFT:
        raise ValidationError(
            "Only DRAFT payslips can be approved."
        )

    salary_record.status      = SalaryRecord.APPROVED
    salary_record.approved_by = approved_by
    salary_record.approved_at = timezone.now()
    salary_record.save(update_fields=[
        "status", "approved_by", "approved_at",
    ])
    return salary_record


@transaction.atomic
def add_salary_payment(
    *,
    salary_record:  SalaryRecord,
    amount:         Decimal | float,
    payment_method: str,
    paid_by,
    reference:      str | None = None,
    notes:          str | None = None,
) -> SalaryPayment:
    """
    Records a salary payment against a payslip.
    Auto-updates total_paid, balance and status on SalaryRecord.

    Status transitions:
    APPROVED → PARTIAL  (partial payment)
    APPROVED → PAID     (full payment in one shot)
    PARTIAL  → PARTIAL  (another partial)
    PARTIAL  → PAID     (final payment clears balance)
    """

    if salary_record.status not in {
        SalaryRecord.APPROVED,
        SalaryRecord.PARTIAL,
    }:
        raise ValidationError(
            f"Cannot add payment to a {salary_record.status} payslip. "
            "Approve it first."
        )

    if payment_method not in dict(SalaryPayment.PAYMENT_METHODS):
        raise ValidationError(
            f"Invalid payment method: {payment_method}"
        )

    amount = _round(amount)

    if amount <= 0:
        raise ValidationError("Payment amount must be greater than zero.")

    if amount > salary_record.balance:
        raise ValidationError(
            f"Payment of {amount} exceeds outstanding balance "
            f"of {salary_record.balance}."
        )

    # ── Create payment ────────────────────────────────
    payment = SalaryPayment.objects.create(
        salary_record=salary_record,
        amount=amount,
        payment_method=payment_method,
        reference=reference,
        notes=notes,
        paid_by=paid_by,
        paid_at=timezone.now(),
    )

    # ── Update denormalized fields on SalaryRecord ────
    salary_record.total_paid = _round(salary_record.total_paid + amount)
    salary_record.balance    = _round(salary_record.net_amount - salary_record.total_paid)

    if salary_record.balance <= 0:
        salary_record.status = SalaryRecord.PAID
    else:
        salary_record.status = SalaryRecord.PARTIAL

    salary_record.save(update_fields=[
        "total_paid", "balance", "status",
    ])

    return payment


@transaction.atomic
def regenerate_payslip(
    *,
    salary_record: SalaryRecord,
    deductions:    Decimal | float | None = None,
    regenerated_by,
) -> SalaryRecord:
    """
    Recalculates a DRAFT payslip — useful when attendance
    records are corrected after initial generation.
    Cannot regenerate APPROVED, PARTIAL or PAID payslips.
    """

    if salary_record.status != SalaryRecord.DRAFT:
        raise ValidationError(
            "Only DRAFT payslips can be regenerated. "
            "Approved or paid payslips are locked."
        )

    employee = salary_record.employee
    year     = salary_record.period_year
    month    = salary_record.period_month

    contract = _get_contract(employee)

    working_days = _working_days_in_month(
        year, month, contract.working_days_per_week
    )

    month_start = date(year, month, 1)
    _, last     = calendar.monthrange(year, month)
    month_end   = date(year, month, last)

    attendance_records = AttendanceRecord.objects.filter(
        employee=employee,
        date__gte=month_start,
        date__lte=month_end,
    )

    days_present = Decimal("0")
    for record in attendance_records:
        days_present += Decimal(str(record.attendance_weight))

    leave_weight           = Decimal(str(contract.leave_pay_weight))
    approved_leaves        = _get_approved_leave_days(employee, year, month)
    attended_dates         = {r.date for r in attendance_records}
    unattended_leave_dates = [
        d for d in approved_leaves if d not in attended_dates
    ]
    days_on_leave = Decimal(str(len(unattended_leave_dates))) * leave_weight

    effective_days = days_present + days_on_leave
    base           = Decimal(str(contract.base_monthly))
    gross          = _round(
        (effective_days / Decimal(str(working_days))) * base
    )

    final_deductions = _round(
        deductions if deductions is not None else salary_record.deductions
    )
    net     = _round(gross - final_deductions)
    balance = net

    salary_record.base_monthly  = base
    salary_record.working_days  = working_days
    salary_record.days_present  = days_present
    salary_record.days_on_leave = days_on_leave
    salary_record.gross_amount  = gross
    salary_record.deductions    = final_deductions
    salary_record.net_amount    = net
    salary_record.balance       = balance
    salary_record.save(update_fields=[
        "base_monthly", "working_days", "days_present",
        "days_on_leave", "gross_amount", "deductions",
        "net_amount", "balance",
    ])

    return salary_record