# hr/models.py

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError


# ======================================================
# EMPLOYEE CONTRACT
# ======================================================

class EmployeeContract(models.Model):

    FULL_TIME  = "FULL_TIME"
    PART_TIME  = "PART_TIME"
    CONTRACT   = "CONTRACT"

    EMPLOYMENT_TYPES = (
        (FULL_TIME, "Full Time"),
        (PART_TIME, "Part Time"),
        (CONTRACT,  "Contract"),
    )

    FULL_PAY = "FULL_PAY"
    HALF_PAY = "HALF_PAY"
    NO_PAY   = "NO_PAY"

    LEAVE_PAY_POLICIES = (
        (FULL_PAY, "Full Pay"),
        (HALF_PAY, "Half Pay"),
        (NO_PAY,   "No Pay"),
    )

    employee = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contract",
    )

    # ── Position ──────────────────────────────────────
    department       = models.CharField(max_length=150)
    position         = models.CharField(max_length=150)
    employment_type  = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_TYPES,
        default=FULL_TIME,
    )
    date_hired       = models.DateField()

    # ── Salary ────────────────────────────────────────
    base_monthly     = models.DecimalField(max_digits=12, decimal_places=2)

    # ── Attendance rules ──────────────────────────────
    check_in_time         = models.TimeField(
        default="09:00",
        help_text="Official start time. Arrivals after this + grace period are LATE.",
    )
    late_threshold_mins   = models.IntegerField(
        default=15,
        help_text="Grace period in minutes before marking as LATE.",
    )
    working_days_per_week = models.IntegerField(
        default=5,
        help_text="Used to calculate expected working days per month.",
    )

    # ── Leave pay policy ──────────────────────────────
    leave_pay_policy = models.CharField(
        max_length=10,
        choices=LEAVE_PAY_POLICIES,
        default=FULL_PAY,
        help_text=(
            "How approved leave days count toward salary. "
            "FULL_PAY=1.0, HALF_PAY=0.5, NO_PAY=0.0"
        ),
    )

    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["employee__name"]
        indexes  = [
            models.Index(fields=["department"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.employee.name} — {self.position}"

    @property
    def leave_pay_weight(self) -> float:
        """Returns the decimal weight for approved leave days."""
        return {
            self.FULL_PAY: 1.0,
            self.HALF_PAY: 0.5,
            self.NO_PAY:   0.0,
        }.get(self.leave_pay_policy, 1.0)


# ======================================================
# ATTENDANCE RECORD
# ======================================================

class AttendanceRecord(models.Model):

    PRESENT  = "PRESENT"
    ABSENT   = "ABSENT"
    LATE     = "LATE"
    HALF_DAY = "HALF_DAY"

    STATUSES = (
        (PRESENT,  "Present"),
        (ABSENT,   "Absent"),
        (LATE,     "Late"),
        (HALF_DAY, "Half Day"),
    )

    SELF    = "SELF"
    MANAGER = "MANAGER"

    SOURCES = (
        (SELF,    "Self"),
        (MANAGER, "Manager"),
    )

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    date     = models.DateField()
    time_in  = models.TimeField(
        null=True, blank=True,
        help_text="Null for ABSENT records.",
    )
    time_out = models.TimeField(
        null=True, blank=True,
        help_text="Null until employee checks out.",
    )
    status = models.CharField(
        max_length=10,
        choices=STATUSES,
        default=PRESENT,
    )
    source = models.CharField(
        max_length=10,
        choices=SOURCES,
        default=SELF,
    )
    notes       = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="recorded_attendance",
        help_text="Null if source=SELF.",
    )
    created_at  = models.DateTimeField(default=timezone.now)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering        = ["-date", "employee__name"]
        unique_together = ("employee", "date")
        indexes         = [
            models.Index(fields=["employee", "date"]),
            models.Index(fields=["date"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.employee.name} | {self.date} | {self.status}"

    @property
    def attendance_weight(self) -> float:
        """
        Weight used in salary calculation.
        PRESENT=1.0, LATE=1.0, HALF_DAY=0.5, ABSENT=0.0
        """
        return {
            self.PRESENT:  1.0,
            self.LATE:     1.0,
            self.HALF_DAY: 0.5,
            self.ABSENT:   0.0,
        }.get(self.status, 0.0)


# ======================================================
# LEAVE REQUEST
# ======================================================

class LeaveRequest(models.Model):

    SICK       = "SICK"
    ANNUAL     = "ANNUAL"
    UNPAID     = "UNPAID"
    MATERNITY  = "MATERNITY"
    PATERNITY  = "PATERNITY"

    LEAVE_TYPES = (
        (SICK,      "Sick Leave"),
        (ANNUAL,    "Annual Leave"),
        (UNPAID,    "Unpaid Leave"),
        (MATERNITY, "Maternity Leave"),
        (PATERNITY, "Paternity Leave"),
    )

    PENDING  = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

    STATUSES = (
        (PENDING,  "Pending"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
    )

    employee   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="leave_requests",
    )
    leave_type = models.CharField(max_length=15, choices=LEAVE_TYPES)
    start_date = models.DateField()
    end_date   = models.DateField()
    reason     = models.TextField(blank=True, null=True)

    status      = models.CharField(
        max_length=10,
        choices=STATUSES,
        default=PENDING,
    )
    reviewed_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reviewed_leaves",
    )
    reviewed_at   = models.DateTimeField(null=True, blank=True)
    review_notes  = models.TextField(blank=True, null=True)
    created_at    = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        indexes  = [
            models.Index(fields=["employee", "status"]),
            models.Index(fields=["start_date", "end_date"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return (
            f"{self.employee.name} | {self.leave_type} | "
            f"{self.start_date} → {self.end_date} | {self.status}"
        )

    def clean(self):
        if self.end_date < self.start_date:
            raise ValidationError("End date cannot be before start date.")

    @property
    def total_days(self) -> int:
        return (self.end_date - self.start_date).days + 1


# ======================================================
# SALARY RECORD
# ======================================================

class SalaryRecord(models.Model):

    DRAFT    = "DRAFT"
    APPROVED = "APPROVED"
    PARTIAL  = "PARTIAL"
    PAID     = "PAID"

    STATUSES = (
        (DRAFT,    "Draft"),
        (APPROVED, "Approved"),
        (PARTIAL,  "Partial"),
        (PAID,     "Paid"),
    )

    employee     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="salary_records",
    )
    period_year  = models.IntegerField()
    period_month = models.IntegerField()

    # ── Attendance snapshot ───────────────────────────
    base_monthly  = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Snapshot of contract base salary at generation time.",
    )
    working_days  = models.IntegerField(
        help_text="Total expected working days in the period.",
    )
    days_present  = models.DecimalField(
        max_digits=6, decimal_places=2,
        help_text="Weighted attendance days (PRESENT=1, HALF_DAY=0.5, LATE=1).",
    )
    days_on_leave = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        help_text="Weighted leave days based on contract leave_pay_policy.",
    )

    # ── Amounts ───────────────────────────────────────
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2)
    deductions   = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Manual deductions — tax, advances, etc.",
    )
    net_amount   = models.DecimalField(max_digits=12, decimal_places=2)

    # ── Payment tracking (denormalized for speed) ─────
    total_paid = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
    )
    balance    = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="net_amount - total_paid",
    )

    # ── Status ────────────────────────────────────────
    status      = models.CharField(
        max_length=10,
        choices=STATUSES,
        default=DRAFT,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="approved_salaries",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering        = ["-period_year", "-period_month", "employee__name"]
        unique_together = ("employee", "period_year", "period_month")
        indexes         = [
            models.Index(fields=["employee", "period_year", "period_month"]),
            models.Index(fields=["status"]),
            models.Index(fields=["period_year", "period_month"]),
        ]

    def __str__(self):
        return (
            f"{self.employee.name} | "
            f"{self.period_year}/{self.period_month:02d} | "
            f"{self.status}"
        )

    @property
    def is_fully_paid(self) -> bool:
        return self.balance <= 0


# ======================================================
# SALARY PAYMENT
# ======================================================

class SalaryPayment(models.Model):

    CASH          = "CASH"
    BANK_TRANSFER = "BANK_TRANSFER"
    MPESA         = "MPESA"

    PAYMENT_METHODS = (
        (CASH,          "Cash"),
        (BANK_TRANSFER, "Bank Transfer"),
        (MPESA,         "M-Pesa"),
    )

    salary_record  = models.ForeignKey(
        SalaryRecord,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount         = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=15, choices=PAYMENT_METHODS)
    reference      = models.CharField(
        max_length=100, null=True, blank=True,
        help_text="Transaction ref, cheque number, M-Pesa code, etc.",
    )
    notes   = models.TextField(blank=True, null=True)
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="salary_payments_made",
    )
    paid_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-paid_at"]
        indexes  = [
            models.Index(fields=["salary_record"]),
            models.Index(fields=["paid_at"]),
        ]

    def __str__(self):
        return (
            f"{self.salary_record.employee.name} | "
            f"{self.payment_method} | {self.amount}"
        )