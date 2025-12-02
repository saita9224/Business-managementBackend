# employees/permissions_loader.py

"""
Scans installed apps for permissions.py containing PERMISSIONS = set([...])
and syncs them into the Permission table.
"""

import importlib
from django.apps import apps
from .models import Permission


def load_permissions():
    for app_config in apps.get_app_configs():
        module_name = f"{app_config.name}.permissions"

        try:
            module = importlib.import_module(module_name)

            if hasattr(module, "PERMISSIONS"):
                app_permissions = getattr(module, "PERMISSIONS")
                print(f"🔍 Loading permissions from: {module_name}")

                for perm in app_permissions:
                    Permission.objects.get_or_create(
                        code=perm,
                        defaults={
                            "name": perm,         # 🔥 FIX: Prevents blank name
                            "description": perm,  # Optional simple description
                        }
                    )

        except ModuleNotFoundError:
            continue

    print("✅ Permission Sync Complete")
