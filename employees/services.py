from django.contrib.auth.models import User
from .models import Employee


def create_employee_account(username, password, role, department, phone):
    # Create User
    user = User.objects.create_user(
        username=username,
        password=password
    )

    # Create Employee profile
    employee = Employee.objects.create(
        user=user,
        role=role,
        department=department,
        phone=phone
    )

    return employee
