# employees/permissions_loader.py

"""
This module automatically loads all permissions from each app’s
permissions.py file and inserts them into the Permission model.

It runs on Django startup and ensures the database always matches
the permission definitions in the code.
"""

import importlib
from django.conf import settings
from django.apps import apps
from .models import Permission


def load_permissions():
    """
    Scans all installed apps for a `permissions.py` file containing
    a PERMISSIONS set, then loads them into the Permission model.
    """

    for app_config in apps.get_app_configs():
        module_name = f"{app_config.name}.permissions"

        try:
            module = importlib.import_module(module_name)

            if hasattr(module, "PERMISSIONS"):
                app_permissions = getattr(module, "PERMISSIONS")

                print(f"🔍 Loading permissions from: {module_name}")

                for perm in app_permissions:
                    Permission.objects.get_or_create(
                        name=perm,
                        defaults={"description": perm}   # simple placeholder
                    )

        except ModuleNotFoundError:
            # App simply doesn’t have a permissions.py file → ignore
            continue

    print("✅ Permission Sync Complete")
