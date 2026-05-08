# employees/management/commands/seed_default_data.py

"""
Seeds a tenant schema with the default Admin role and assigns
all currently loaded permissions to it.

Run inside a specific tenant schema:
    python manage.py seed_default_data --schema hoppers

Or for all tenants:
    python manage.py seed_default_data --all-tenants

This command does NOT create an employee — admins register
themselves via the googleAuth or requestRegistration mutations.
The seeder only ensures the Admin role and its permissions exist.
"""

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Seed default Admin role and permissions into a tenant schema."

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            help="Seed a specific tenant schema by name.",
        )
        parser.add_argument(
            "--all-tenants",
            action="store_true",
            help="Seed all tenant schemas.",
        )

    def handle(self, *args, **options):
        from django_tenants.utils import schema_context, get_tenant_model

        schema    = options.get("schema")
        all_tenants = options.get("all_tenants")

        if not schema and not all_tenants:
            self.stderr.write(self.style.ERROR(
                "Provide --schema <name> or --all-tenants"
            ))
            return

        TenantModel = get_tenant_model()

        if all_tenants:
            tenants = TenantModel.objects.exclude(schema_name="public")
        else:
            tenants = TenantModel.objects.filter(schema_name=schema)
            if not tenants.exists():
                self.stderr.write(self.style.ERROR(
                    f"No tenant found with schema_name='{schema}'"
                ))
                return

        for tenant in tenants:
            self.stdout.write(f"\n── Seeding: {tenant.name} ({tenant.schema_name})")
            with schema_context(tenant.schema_name):
                self._seed(tenant.schema_name)

        self.stdout.write(self.style.SUCCESS("\n🎉 Seeding complete."))

    @transaction.atomic
    def _seed(self, schema_name: str):
        from employees.models import Role, Permission, RolePermission

        # ── 1. Ensure Admin role exists ────────────────────────────
        admin_role, created = Role.objects.get_or_create(
            name="Admin",
            defaults={"description": "Full platform access — all permissions granted"},
        )
        if created:
            self.stdout.write(self.style.SUCCESS("   ✔ Admin role created"))
        else:
            self.stdout.write("   Admin role already exists")

        # ── 2. Assign ALL current permissions to Admin ─────────────
        permissions = Permission.objects.all()

        if not permissions.exists():
            self.stdout.write(self.style.WARNING(
                "   ⚠ No permissions found. "
                "Run sync_permissions first:\n"
                "   python manage.py sync_permissions --all-tenants"
            ))
            return

        created_count = 0
        for perm in permissions:
            _, was_created = RolePermission.objects.get_or_create(
                role=admin_role,
                permission=perm,
            )
            if was_created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"   ✔ {created_count} new permission(s) assigned to Admin "
            f"({permissions.count()} total)"
        ))