from django.core.management.base import BaseCommand
from employees.models import Employee, Role, Permission, RolePermission


class Command(BaseCommand):
    help = "Seeds the database with initial roles, permissions, and admin user."

    def handle(self, *args, **kwargs):

        # 1. Create ADMIN role
        admin_role, created = Role.objects.get_or_create(
            name="Admin",
            defaults={"description": "System Administrator"}
        )

        if created:
            self.stdout.write(self.style.SUCCESS("✔ Admin role created"))
        else:
            self.stdout.write("Admin role already exists")

        # 2. Assign ALL permissions to Admin
        permissions = Permission.objects.all()

        for perm in permissions:
            RolePermission.objects.get_or_create(role=admin_role, permission=perm)

        self.stdout.write(self.style.SUCCESS("✔ All permissions assigned to Admin"))

        # 3. Create default admin user
        admin_email = "admin@example.com"

        if not Employee.objects.filter(email=admin_email).exists():
            admin = Employee.objects.create(
                name="System Administrator",
                email=admin_email,
                phone="",
                is_active=True,
                password=""  # will be replaced below
            )
            admin.set_password("Admin123!")
            admin.roles.add(admin_role)

            self.stdout.write(self.style.SUCCESS(
                f"✔ Admin employee created (email: {admin_email}, password: Admin123!)"
            ))
        else:
            self.stdout.write("Admin employee already exists")

        self.stdout.write(self.style.SUCCESS("🎉 Seeding complete!"))
