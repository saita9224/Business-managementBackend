# employees/seeders.py

from employees.models import Employee, Role

def seed_initial_data():

    if Employee.objects.exists():
        return

    admin_role, _ = Role.objects.get_or_create(name="Admin")

    employee = Employee.objects.create(
        name="System Admin",
        email="admin@example.com",
        phone="0000000000",
    )
    employee.set_password("Admin123!")
    employee.save()          # ← this was missing

    employee.roles.add(admin_role)

    print("🌱 Default admin created:")
    print("  email: admin@example.com")
    print("  password: Admin123!")