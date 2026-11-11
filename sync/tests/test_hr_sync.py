from datetime import date

import pytest
from django_tenants.utils import schema_context

from employees.models import Employee
from hr.models import EmployeeContract, LeaveRequest
from hr.services import request_leave, self_check_in, self_check_out
from sync.registry import SYNC_MUTATION_REGISTRY
from sync.types import SyncMutationTypeEnum


@pytest.mark.django_db
def test_hr_offline_mutations_are_registered():
    assert SYNC_MUTATION_REGISTRY[SyncMutationTypeEnum.SELF_CHECK_IN]["permission"] == "hr.self_checkin"
    assert SYNC_MUTATION_REGISTRY[SyncMutationTypeEnum.SELF_CHECK_OUT]["permission"] == "hr.self_checkin"
    assert SYNC_MUTATION_REGISTRY[SyncMutationTypeEnum.REQUEST_LEAVE]["permission"] == "hr.request_leave"


@pytest.mark.django_db(transaction=True)
def test_replayed_hr_offline_mutations_are_idempotent(tenant_schema):
    with schema_context(tenant_schema.schema_name):
        employee = Employee.objects.create_user(
            email="hr-offline@example.test",
            password="test-password",
            name="HR Offline Test",
        )
        EmployeeContract.objects.create(
            employee=employee,
            department="Front Office",
            position="Receptionist",
            date_hired=date(2026, 1, 1),
            base_monthly=30000,
        )

        leave_values = {
            "employee": employee,
            "leave_type": LeaveRequest.ANNUAL,
            "start_date": date(2026, 12, 1),
            "end_date": date(2026, 12, 3),
            "client_id": "leave-client-1",
        }
        first_leave = request_leave(**leave_values)
        replayed_leave = request_leave(**leave_values)
        assert first_leave.pk == replayed_leave.pk
        assert LeaveRequest.objects.count() == 1

        checked_in = self_check_in(employee=employee, client_id="check-in-client-1")
        assert self_check_in(employee=employee, client_id="check-in-client-1").pk == checked_in.pk
        checked_out = self_check_out(employee=employee, client_id="check-out-client-1")
        replayed_checkout = self_check_out(employee=employee, client_id="check-out-client-1")
        assert checked_out.pk == replayed_checkout.pk
        assert self_check_in(employee=employee, client_id="check-in-client-1").pk == checked_in.pk
        assert checked_out.time_out is not None
