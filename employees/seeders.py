# employees/seeders.py

from employees.models import Employee, Role

def seed_initial_data():

    # Avoid duplicates
    if Employee.objects.exists():
        return

    # Create default role
    admin_role, _ = Role.objects.get_or_create(name="Admin")

    # Create first admin employee
    employee = Employee.objects.create(
        name="System Admin",
        email="admin@example.com",
        phone="0000000000",
    )
    employee.set_password("Admin123!")

    # Assign role
    employee.roles.add(admin_role)

    print("🌱 Default admin created:")
    print("  email: admin@example.com")
    print("  password: Admin123!")
