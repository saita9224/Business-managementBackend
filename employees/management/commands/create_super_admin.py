# employees/management/commands/create_super_admin.py

"""
One-time management command to create the platform SuperAdmin.

Run once after initial deployment:
    python manage.py create_super_admin

Subsequent runs are safe — they do nothing if a SuperAdmin
already exists. The account can only be created from the
server terminal, never via GraphQL.
"""

import getpass
from django.core.management.base import BaseCommand
from django.core.validators import validate_email
from django.core.exceptions import ValidationError


class Command(BaseCommand):
    help = "Create the one-time platform SuperAdmin account."

    def handle(self, *args, **kwargs):
        from tenants.models import SuperAdmin

        # ── Guard: only one SuperAdmin ever ───────────────────────
        if SuperAdmin.objects.exists():
            self.stdout.write(
                self.style.WARNING(
                    "⚠ A SuperAdmin account already exists. "
                    "Only one SuperAdmin is permitted.\n"
                    "  To reset it, use: python manage.py reset_super_admin"
                )
            )
            return

        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n🔐 Creating Platform SuperAdmin\n"
            "   This account has access to all tenants.\n"
            "   Store the credentials securely.\n"
        ))

        # ── Collect name ───────────────────────────────────────────
        name = input("Full name: ").strip()
        if not name:
            self.stderr.write(self.style.ERROR("Name cannot be empty."))
            return

        # ── Collect and validate email ─────────────────────────────
        email = input("Email: ").strip().lower()
        try:
            validate_email(email)
        except ValidationError:
            self.stderr.write(self.style.ERROR(f"Invalid email: {email}"))
            return

        # ── Collect and confirm password ───────────────────────────
        while True:
            password = getpass.getpass("Password: ")
            if len(password) < 10:
                self.stderr.write(
                    self.style.ERROR("Password must be at least 10 characters.")
                )
                continue

            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                self.stderr.write(self.style.ERROR("Passwords do not match."))
                continue

            break

        # ── Create ─────────────────────────────────────────────────
        admin = SuperAdmin(name=name, email=email, is_active=True)
        admin.set_password(password)
        admin.save()

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ SuperAdmin created successfully.\n"
            f"   Email: {email}\n"
            f"   Use the superAdminLogin mutation at /super/graphql/ to authenticate.\n"
        ))