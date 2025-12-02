import pytest
from types import SimpleNamespace
from employees.models import Employee, Role, Permission, RolePermission, EmployeeRole


@pytest.fixture
def employee():
    return Employee.objects.create(
        name="User",
        email="user@example.com",
        password="Pass123!"  # hashing not required here
    )


@pytest.fixture
def employee_factory():
    def create(**kwargs):
        return Employee.objects.create(
            name=kwargs.get("name", "User"),
            email=kwargs.get("email", "user@example.com"),
            password=kwargs.get("password", "Pass123!")
        )
    return create


@pytest.fixture
def employee_with_role_permission():
    user = Employee.objects.create(
        name="Admin",
        email="admin@example.com"
    )

    role = Role.objects.create(name="Manager")
    perm = Permission.objects.create(code="employees.view", name="Employees View")

    RolePermission.objects.create(role=role, permission=perm)
    EmployeeRole.objects.create(employee=user, role=role)

    return user


@pytest.fixture
def info_context():
    def build(user):
        return SimpleNamespace(context={"user": user})
    return build
