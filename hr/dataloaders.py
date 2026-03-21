# hr/dataloaders.py

from collections import defaultdict
from typing import List, Optional

from asgiref.sync import sync_to_async
from strawberry.dataloader import DataLoader

from .models import (
    EmployeeContract,
    AttendanceRecord,
    LeaveRequest,
    SalaryRecord,
    SalaryPayment,
)


# ──────────────────────────────────────────────────────
# CONTRACT BY EMPLOYEE
# One-to-one — returns a single contract or None
# ──────────────────────────────────────────────────────

async def load_contract_by_employee(
    keys: List[int],
) -> List[Optional[EmployeeContract]]:
    contracts = await sync_to_async(list)(
        EmployeeContract.objects.filter(employee_id__in=keys)
    )
    contract_map = {c.employee_id: c for c in contracts}
    return [contract_map.get(k) for k in keys]


# ──────────────────────────────────────────────────────
# ATTENDANCE RECORDS BY EMPLOYEE
# Returns all records for each employee — caller filters
# by date range as needed
# ──────────────────────────────────────────────────────

async def load_attendance_by_employee(
    keys: List[int],
) -> List[List[AttendanceRecord]]:
    records = await sync_to_async(list)(
        AttendanceRecord.objects
        .filter(employee_id__in=keys)
        .order_by("-date")
    )
    grouped: dict[int, list] = defaultdict(list)
    for r in records:
        grouped[r.employee_id].append(r)
    return [grouped.get(k, []) for k in keys]


# ──────────────────────────────────────────────────────
# LEAVE REQUESTS BY EMPLOYEE
# ──────────────────────────────────────────────────────

async def load_leave_requests_by_employee(
    keys: List[int],
) -> List[List[LeaveRequest]]:
    requests = await sync_to_async(list)(
        LeaveRequest.objects
        .filter(employee_id__in=keys)
        .select_related("reviewed_by")
        .order_by("-created_at")
    )
    grouped: dict[int, list] = defaultdict(list)
    for r in requests:
        grouped[r.employee_id].append(r)
    return [grouped.get(k, []) for k in keys]


# ──────────────────────────────────────────────────────
# SALARY RECORDS BY EMPLOYEE
# ──────────────────────────────────────────────────────

async def load_salary_records_by_employee(
    keys: List[int],
) -> List[List[SalaryRecord]]:
    records = await sync_to_async(list)(
        SalaryRecord.objects
        .filter(employee_id__in=keys)
        .select_related("approved_by")
        .order_by("-period_year", "-period_month")
    )
    grouped: dict[int, list] = defaultdict(list)
    for r in records:
        grouped[r.employee_id].append(r)
    return [grouped.get(k, []) for k in keys]


# ──────────────────────────────────────────────────────
# SALARY PAYMENTS BY SALARY RECORD
# ──────────────────────────────────────────────────────

async def load_payments_by_salary_record(
    keys: List[int],
) -> List[List[SalaryPayment]]:
    payments = await sync_to_async(list)(
        SalaryPayment.objects
        .filter(salary_record_id__in=keys)
        .select_related("paid_by")
        .order_by("-paid_at")
    )
    grouped: dict[int, list] = defaultdict(list)
    for p in payments:
        grouped[p.salary_record_id].append(p)
    return [grouped.get(k, []) for k in keys]


# ──────────────────────────────────────────────────────
# LOADER FACTORY (REQUEST SCOPED)
# ──────────────────────────────────────────────────────

def create_hr_dataloaders() -> dict:
    """
    Must be created per request to ensure correct caching
    and no data leakage across users.
    """
    return {
        "contract_by_employee":          DataLoader(load_fn=load_contract_by_employee),
        "attendance_by_employee":        DataLoader(load_fn=load_attendance_by_employee),
        "leave_requests_by_employee":    DataLoader(load_fn=load_leave_requests_by_employee),
        "salary_records_by_employee":    DataLoader(load_fn=load_salary_records_by_employee),
        "payments_by_salary_record":     DataLoader(load_fn=load_payments_by_salary_record),
    }