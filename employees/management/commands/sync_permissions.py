# employees/management/commands/sync_permissions.py

"""
Sync permission codes from every app's permissions.py into the DB.

After syncing, run seed_default_data to assign new permissions
to the Admin role in each tenant schema.

Typical post-deploy sequence when new permissions are added:
    python manage.py sync_permissions --all-tenants
    python manage.py seed_default_data --all-tenants
"""

from django.core.management.base import BaseCommand
from employees.permissions_loader import (
    load_permissions,
    load_permissions_all_tenants,
)


class Command(BaseCommand):
    help = "Sync permission codes from permissions.py files into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--all-tenants",
            action="store_true",
            help="Sync into every tenant schema (default: current schema only).",
        )

    def handle(self, *args, **options):
        if options["all_tenants"]:
            self.stdout.write("Syncing permissions across all tenants...")
            result = load_permissions_all_tenants()
        else:
            self.stdout.write("Syncing permissions for current schema...")
            result = load_permissions()

        self.stdout.write(self.style.SUCCESS(
            f"Done — created: {result['created']}, "
            f"updated: {result['updated']}, "
            f"unchanged: {result['unchanged']}"
        ))

        # Remind the developer to assign new permissions to Admin
        if result["created"] > 0:
            self.stdout.write(self.style.WARNING(
                f"\n{result['created']} new permission(s) were created.\n"
                "Assign them to the Admin role by running:\n"
                "  python manage.py seed_default_data --all-tenants"
            ))