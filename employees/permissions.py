# employees/permissions.py

"""
Permissions for the Employees app.
permissions_loader.py loads these into the DB on startup.
"""

from functools import lru_cache
from .models import RolePermission


PERMISSIONS = {
    "employee.view",
    "employee.create",
    "employee.update",
    "employee.delete",
    "role.create",
    "role.update",
    "role.delete",
}

PERMISSION_META = {
    "employee.view":   ("View Employees",       "Can view the employee list and profiles"),
    "employee.create": ("Create Employees",      "Can onboard new employees"),
    "employee.update": ("Edit Employees",        "Can update employee details and roles"),
    "employee.delete": ("Delete Employees",      "Can permanently remove an employee"),
    "role.create":     ("Create Roles",          "Can create new roles and permission groups"),
    "role.update":     ("Edit Roles",            "Can modify role permissions"),
    "role.delete":     ("Delete Roles",          "Can delete roles from the system"),
}


# ── Permission resolution engine ──────────────────────

@lru_cache(maxsize=100)
def get_permissions_for_role(role_name: str) -> set:
    perms = (
        RolePermission.objects
        .filter(role__name=role_name)
        .select_related("permission")
    )
    return set(p.permission.code for p in perms)


def clear_permission_cache():
    get_permissions_for_role.cache_clear()