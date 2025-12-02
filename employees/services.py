# employees/services.py

from .models import Employee, Role, EmployeeRole


def create_employee(name, email, phone, password, role_ids: list):
    """
    Creates an employee and assigns roles through the EmployeeRole table.
    
    role_ids → list of role primary keys
    """

    # Create employee
    employee = Employee.objects.create(
        name=name,
        email=email,
        phone=phone
    )

    # Set hashed password
    employee.set_password(password)

    # Assign roles
    for role_id in role_ids:
        role = Role.objects.get(id=role_id)
        EmployeeRole.objects.create(employee=employee, role=role)

    return employee
