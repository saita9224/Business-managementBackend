from django.core.management.base import BaseCommand
from django.db import transaction
from employees.models import Employee, Role, Permission, RolePermission


class Command(BaseCommand):
    help = "Seeds the database with initial roles, permissions, and admin user."

    @transaction.atomic
    def handle(self, *args, **kwargs):

        # 1️⃣ Create ADMIN role
        admin_role, created = Role.objects.get_or_create(
            name="Admin",
            defaults={"description": "System Administrator"}
        )

        if created:
            self.stdout.write(self.style.SUCCESS("✔ Admin role created"))
        else:
            self.stdout.write("Admin role already exists")

        # 2️⃣ Assign ALL permissions to Admin (without duplicates)
        permissions = Permission.objects.all()

        for perm in permissions:
            RolePermission.objects.get_or_create(
                role=admin_role,
                permission=perm
            )

        self.stdout.write(self.style.SUCCESS("✔ All permissions assigned to Admin"))

        # 3️⃣ Create default admin user
        admin_email = "admin@example.com"

        admin, created = Employee.objects.get_or_create(
            email=admin_email,
            defaults={
                "name": "System Administrator",
                "phone": "",
                "is_active": True,
            }
        )

        if created:
            # Proper way to set password
            admin.set_password("Admin123!")
            admin.save()

            admin.roles.add(admin_role)

            self.stdout.write(self.style.SUCCESS(
                f"✔ Admin employee created (email: {admin_email}, password: Admin123!)"
            ))
        else:
            self.stdout.write("Admin employee already exists")

        self.stdout.write(self.style.SUCCESS("🎉 Seeding complete!"))
