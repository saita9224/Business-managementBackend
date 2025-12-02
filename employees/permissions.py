# employees/permissions.py

"""
This file defines all permissions for the Employees app.
permissions_loader.py will automatically load them into the DB
during Django startup.
"""

# -------------------------------
# PERMISSIONS FOR THIS APP
# -------------------------------

PERMISSIONS = {
    "employee.view",
    "employee.create",
    "employee.update",
    "employee.delete",
}

# -------------------------------
# PERMISSION RESOLUTION ENGINE
# -------------------------------
from functools import lru_cache
from .models import RolePermission


@lru_cache(maxsize=100)
def get_permissions_for_role(role_name: str) -> set:
    """
    Returns a set of permission codes (strings) assigned to a given role.
    Uses caching to avoid repeated DB hits.
    """
    perms = (
        RolePermission.objects
        .filter(role__name=role_name)
        .select_related("permission")
    )
    return set(p.permission.code for p in perms)


def clear_permission_cache():
    """Clears the permission cache after updates."""
    get_permissions_for_role.cache_clear()
