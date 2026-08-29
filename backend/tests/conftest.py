import pytest
import uuid
from types import SimpleNamespace
from django.db import connection
from django_tenants.utils import schema_context
from employees.models import Employee, Role, Permission, RolePermission, EmployeeRole
from tenants.models import Business, Domain


@pytest.fixture
def tenant_schema(db):
    schema_name = f"test_{uuid.uuid4().hex[:8]}"
    tenant = Business.objects.create(
        schema_name=schema_name,
        name="Test Business",
    )
    Domain.objects.create(
        tenant=tenant,
        domain=f"{schema_name}.test.localhost",
        is_primary=True,
    )

    connection.set_tenant(tenant)
    try:
        yield tenant
    finally:
        connection.set_schema_to_public()
        tenant.delete()


@pytest.fixture
def employee(tenant_schema):
    with schema_context(tenant_schema.schema_name):
        return Employee.objects.create(
            name="User",
            email="user@example.com",
            password="Pass123!"  # hashing not required here
        )


@pytest.fixture
def employee_factory(tenant_schema):
    def create(**kwargs):
        with schema_context(tenant_schema.schema_name):
            return Employee.objects.create(
                name=kwargs.get("name", "User"),
                email=kwargs.get("email", "user@example.com"),
                password=kwargs.get("password", "Pass123!")
            )
    return create


@pytest.fixture
def employee_with_role_permission(tenant_schema):
    with schema_context(tenant_schema.schema_name):
        user = Employee.objects.create(
            name="Admin",
            email="admin@example.com"
        )

        role = Role.objects.create(name="Manager")
        perm = Permission.objects.create(
            code="employee.view",
            name="Employee View",
            description="Can view employees",
        )

        RolePermission.objects.create(role=role, permission=perm)
        EmployeeRole.objects.create(employee=user, role=role)

    return user


@pytest.fixture
def info_context():
    def build(user):
        return SimpleNamespace(context={"user": user})
    return build
