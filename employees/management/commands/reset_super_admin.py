# employees/management/commands/reset_super_admin.py

"""
Emergency command to reset the SuperAdmin password.
Requires confirmation before proceeding.
"""

import getpass
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Reset the platform SuperAdmin password."

    def handle(self, *args, **kwargs):
        from tenants.models import SuperAdmin

        try:
            admin = SuperAdmin.objects.get()
        except SuperAdmin.DoesNotExist:
            self.stderr.write(self.style.ERROR(
                "No SuperAdmin exists. Run: python manage.py create_super_admin"
            ))
            return

        self.stdout.write(self.style.WARNING(
            f"\n⚠ Resetting password for SuperAdmin: {admin.email}\n"
        ))

        confirm = input("Type CONFIRM to proceed: ").strip()
        if confirm != "CONFIRM":
            self.stdout.write("Aborted.")
            return

        while True:
            password = getpass.getpass("New password: ")
            if len(password) < 10:
                self.stderr.write(
                    self.style.ERROR("Password must be at least 10 characters.")
                )
                continue

            confirm_pw = getpass.getpass("Confirm new password: ")
            if password != confirm_pw:
                self.stderr.write(self.style.ERROR("Passwords do not match."))
                continue

            break

        admin.set_password(password)
        admin.save()

        self.stdout.write(self.style.SUCCESS("✅ SuperAdmin password reset successfully."))