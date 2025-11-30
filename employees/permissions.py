# employees/permissions.py (fixed)
from functools import lru_cache
from .models import RolePermission

@lru_cache(maxsize=100)
def get_permissions_for_role(role_name: str) -> set:
    # Query the RolePermission table and return a set of permission codes (strings)
    perms = RolePermission.objects.filter(role__name=role_name).select_related("permission")
    return set(p.permission.code for p in perms)

def clear_permission_cache():
    get_permissions_for_role.cache_clear()
