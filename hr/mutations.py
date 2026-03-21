# hr/mutations.py

from typing import Optional, List
from datetime import date, time
from decimal import Decimal

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
)
from .types import (
    EmployeeContractType,
    AttendanceRecordType,
    LeaveRequestType,
    SalaryRecordType,
    SalaryPaymentType,
    wrap_contract,
    wrap_attendance,
    wrap_leave_request,
    wrap_salary_record,
    wrap_salary_payment,
)
from .services import (
    create_contract          as svc_create_contract,
    update_contract          as svc_update_contract,
    self_check_in            as svc_self_check_in,
    self_check_out           as svc_self_check_out,
    record_attendance        as svc_record_attendance,
    manager_check_out        as svc_manager_check_out,
    request_leave            as svc_request_leave,
    review_leave             as svc_review_leave,
    generate_payslip         as svc_generate_payslip,
    approve_payslip          as svc_approve_payslip,
    add_salary_payment       as svc_add_salary_payment,
    regenerate_payslip       as svc_regenerate_payslip,
)


# ======================================================
# INPUT TYPES
# ======================================================

@strawberry.input
class CreateContractInput:
    employee_id:           strawberry.ID
    department:            str
    position:              str
    employment_type:       str
    date_hired:            date
    base_monthly:          float
    check_in_time:         time
    late_threshold_mins:   int  = 15
    working_days_per_week: int  = 5
    leave_pay_policy:      str  = "FULL_PAY"


@strawberry.input
class UpdateContractInput:
    contract_id:           strawberry.ID
    department:            Optional[str]   = None
    position:              Optional[str]   = None
    employment_type:       Optional[str]   = None
    base_monthly:          Optional[float] = None
    check_in_time:         Optional[time]  = None
    late_threshold_mins:   Optional[int]   = None
    working_days_per_week: Optional[int]   = None
    leave_pay_policy:      Optional[str]   = None
    is_active:             Optional[bool]  = None


@strawberry.input
class RecordAttendanceInput:
    employee_id:     strawberry.ID
    attendance_date: date
    status:          str
    time_in:         Optional[time] = None
    time_out:        Optional[time] = None
    notes:           Optional[str]  = None


@strawberry.input
class ManagerCheckOutInput:
    employee_id:     strawberry.ID
    attendance_date: date
    time_out:        time


@strawberry.input
class RequestLeaveInput:
    leave_type:  str
    start_date:  date
    end_date:    date
    reason:      Optional[str] = None


@strawberry.input
class ReviewLeaveInput:
    leave_request_id: strawberry.ID
    status:           str
    review_notes:     Optional[str] = None


@strawberry.input
class GeneratePayslipInput:
    employee_id: strawberry.ID
    year:        int
    month:       int
    deductions:  float = 0.0


@strawberry.input
class AddSalaryPaymentInput:
    salary_record_id: strawberry.ID
    amount:           float
    payment_method:   str
    reference:        Optional[str] = None
    notes:            Optional[str] = None


@strawberry.input
class RegeneratePayslipInput:
    salary_record_id: strawberry.ID
    deductions:       Optional[float] = None


# ======================================================
# MUTATIONS
# ======================================================

@strawberry.type
class HRMutation:

    # ── CONTRACTS ─────────────────────────────────────────

    @strawberry.mutation
    @permission_required("hr.manage_contracts")
    async def create_contract(
        self,
        info:  Info,
        input: CreateContractInput,
    ) -> EmployeeContractType:

        from employees.models import Employee

        def run():
            try:
                employee = Employee.objects.get(pk=int(input.employee_id))
            except Employee.DoesNotExist:
                raise ValueError("Employee not found.")
            return svc_create_contract(
                employee=employee,
                department=input.department,
                position=input.position,
                employment_type=input.employment_type,
                date_hired=input.date_hired,
                base_monthly=input.base_monthly,
                check_in_time=input.check_in_time,
                late_threshold_mins=input.late_threshold_mins,
                working_days_per_week=input.working_days_per_week,
                leave_pay_policy=input.leave_pay_policy,
            )

        try:
            contract = await sync_to_async(run)()
        except Exception as e:
            raise GraphQLError(str(e))

        return wrap_contract(contract)

    @strawberry.mutation
    @permission_required("hr.manage_contracts")
    async def update_contract(
        self,
        info:  Info,
        input: UpdateContractInput,
    ) -> EmployeeContractType:

        def run():
            try:
                contract = EmployeeContract.objects.get(
                    pk=int(input.contract_id)
                )
            except EmployeeContract.DoesNotExist:
                raise ValueError("Contract not found.")
            return svc_update_contract(
                contract=contract,
                department=input.department,
                position=input.position,
                employment_type=input.employment_type,
                base_monthly=input.base_monthly,
                check_in_time=input.check_in_time,
                late_threshold_mins=input.late_threshold_mins,
                working_days_per_week=input.working_days_per_week,
                leave_pay_policy=input.leave_pay_policy,
                is_active=input.is_active,
            )

        try:
            contract = await sync_to_async(run)()
        except Exception as e:
            raise GraphQLError(str(e))

        return wrap_contract(contract)

    # ── ATTENDANCE ────────────────────────────────────────

    @strawberry.mutation
    @permission_required("hr.self_checkin")
    async def self_check_in(
        self,
        info: Info,
    ) -> AttendanceRecordType:
        """Employee checks themselves in."""
        employee = info.context.user

        try:
            record = await sync_to_async(svc_self_check_in)(
                employee=employee,
            )
        except Exception as e:
            raise GraphQLError(str(e))

        return wrap_attendance(record)

    @strawberry.mutation
    @permission_required("hr.self_checkin")
    async def self_check_out(
        self,
        info: Info,
    ) -> AttendanceRecordType:
        """Employee checks themselves out."""
        employee = info.context.user

        try:
            record = await sync_to_async(svc_self_check_out)(
                employee=employee,
            )
        except Exception as e:
            raise GraphQLError(str(e))

        return wrap_attendance(record)

    @strawberry.mutation
    @permission_required("hr.manage_attendance")
    async def record_attendance(
        self,
        info:  Info,
        input: RecordAttendanceInput,
    ) -> AttendanceRecordType:
        """Manager records attendance for any employee."""
        manager = info.context.user

        from employees.models import Employee

        def run():
            try:
                employee = Employee.objects.get(pk=int(input.employee_id))
            except Employee.DoesNotExist:
                raise ValueError("Employee not found.")
            return svc_record_attendance(
                employee=employee,
                recorded_by=manager,
                attendance_date=input.attendance_date,
                status=input.status,
                time_in=input.time_in,
                time_out=input.time_out,
                notes=input.notes,
            )

        try:
            record = await sync_to_async(run)()
        except Exception as e:
            raise GraphQLError(str(e))

        return wrap_attendance(record)

    @strawberry.mutation
    @permission_required("hr.manage_attendance")
    async def manager_check_out(
        self,
        info:  Info,
        input: ManagerCheckOutInput,
    ) -> AttendanceRecordType:
        """Manager records checkout time for an employee."""
        manager = info.context.user

        from employees.models import Employee

        def run():
            try:
                employee = Employee.objects.get(pk=int(input.employee_id))
            except Employee.DoesNotExist:
                raise ValueError("Employee not found.")
            return svc_manager_check_out(
                employee=employee,
                recorded_by=manager,
                attendance_date=input.attendance_date,
                time_out=input.time_out,
            )

        try:
            record = await sync_to_async(run)()
        except Exception as e:
            raise GraphQLError(str(e))

        return wrap_attendance(record)

    # ── LEAVE ─────────────────────────────────────────────

    @strawberry.mutation
    @permission_required("hr.request_leave")
    async def request_leave(
        self,
        info:  Info,
        input: RequestLeaveInput,
    ) -> LeaveRequestType:
        """Employee submits a leave request."""
        employee = info.context.user

        try:
            leave = await sync_to_async(svc_request_leave)(
                employee=employee,
                leave_type=input.leave_type,
                start_date=input.start_date,
                end_date=input.end_date,
                reason=input.reason,
            )
        except Exception as e:
            raise GraphQLError(str(e))

        return wrap_leave_request(leave)

    @strawberry.mutation
    @permission_required("hr.manage_leave")
    async def review_leave(
        self,
        info:  Info,
        input: ReviewLeaveInput,
    ) -> LeaveRequestType:
        """Manager approves or rejects a leave request."""
        manager = info.context.user

        def run():
            try:
                leave = LeaveRequest.objects.select_related(
                    "employee", "reviewed_by"
                ).get(pk=int(input.leave_request_id))
            except LeaveRequest.DoesNotExist:
                raise ValueError("Leave request not found.")
            return svc_review_leave(
                leave_request=leave,
                reviewed_by=manager,
                status=input.status,
                review_notes=input.review_notes,
            )

        try:
            leave = await sync_to_async(run)()
        except Exception as e:
            raise GraphQLError(str(e))

        return wrap_leave_request(leave)

    # ── SALARY ────────────────────────────────────────────

    @strawberry.mutation
    @permission_required("hr.manage_salary")
    async def generate_payslip(
        self,
        info:  Info,
        input: GeneratePayslipInput,
    ) -> SalaryRecordType:
        """Manager generates a DRAFT payslip for an employee."""
        manager = info.context.user

        from employees.models import Employee

        def run():
            try:
                employee = Employee.objects.get(pk=int(input.employee_id))
            except Employee.DoesNotExist:
                raise ValueError("Employee not found.")
            return svc_generate_payslip(
                employee=employee,
                year=input.year,
                month=input.month,
                deductions=Decimal(str(input.deductions)),
                generated_by=manager,
            )

        try:
            record = await sync_to_async(run)()
        except Exception as e:
            raise GraphQLError(str(e))

        return wrap_salary_record(record)

    @strawberry.mutation
    @permission_required("hr.manage_salary")
    async def approve_payslip(
        self,
        info:             Info,
        salary_record_id: strawberry.ID,
    ) -> SalaryRecordType:
        """Manager approves a DRAFT payslip."""
        manager = info.context.user

        def run():
            try:
                record = SalaryRecord.objects.select_related(
                    "employee", "approved_by"
                ).get(pk=int(salary_record_id))
            except SalaryRecord.DoesNotExist:
                raise ValueError("Salary record not found.")
            return svc_approve_payslip(
                salary_record=record,
                approved_by=manager,
            )

        try:
            record = await sync_to_async(run)()
        except Exception as e:
            raise GraphQLError(str(e))

        return wrap_salary_record(record)

    @strawberry.mutation
    @permission_required("hr.manage_salary")
    async def add_salary_payment(
        self,
        info:  Info,
        input: AddSalaryPaymentInput,
    ) -> SalaryPaymentType:
        """
        Records a payment against an approved payslip.
        Auto-updates balance and transitions status:
        APPROVED → PARTIAL → PAID
        """
        manager = info.context.user

        def run():
            try:
                record = SalaryRecord.objects.get(
                    pk=int(input.salary_record_id)
                )
            except SalaryRecord.DoesNotExist:
                raise ValueError("Salary record not found.")
            return svc_add_salary_payment(
                salary_record=record,
                amount=Decimal(str(input.amount)),
                payment_method=input.payment_method,
                paid_by=manager,
                reference=input.reference,
                notes=input.notes,
            )

        try:
            payment = await sync_to_async(run)()
        except Exception as e:
            raise GraphQLError(str(e))

        return wrap_salary_payment(payment)

    @strawberry.mutation
    @permission_required("hr.manage_salary")
    async def regenerate_payslip(
        self,
        info:  Info,
        input: RegeneratePayslipInput,
    ) -> SalaryRecordType:
        """
        Recalculates a DRAFT payslip after attendance corrections.
        Cannot regenerate APPROVED, PARTIAL or PAID payslips.
        """
        manager = info.context.user

        def run():
            try:
                record = SalaryRecord.objects.select_related(
                    "employee", "approved_by"
                ).get(pk=int(input.salary_record_id))
            except SalaryRecord.DoesNotExist:
                raise ValueError("Salary record not found.")
            return svc_regenerate_payslip(
                salary_record=record,
                deductions=(
                    Decimal(str(input.deductions))
                    if input.deductions is not None
                    else None
                ),
                regenerated_by=manager,
            )

        try:
            record = await sync_to_async(run)()
        except Exception as e:
            raise GraphQLError(str(e))

        return wrap_salary_record(record)