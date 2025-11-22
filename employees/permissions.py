# employees/permissions.py

from functools import lru_cache
from .models import Permission, RolePermission


# ---------------------------------------------------
# GET ALL PERMISSIONS FOR A ROLE (DYNAMIC + CACHED)
# ---------------------------------------------------

@lru_cache(maxsize=100)
def get_permissions_for_role(role_name: str) -> set:
    """
    Returns a SET of permission strings assigned to a role.
    Uses database-driven permissions and caches results.
    """

    # Query all permissions linked to this role
    perms = RolePermission.objects.filter(role__name=role_name)

    # Convert list of Permission objects → set of codes
    return set(p.permission.code for p in perms)


# ---------------------------------------------------
# ADMIN: CLEAR CACHE WHEN PERMISSIONS CHANGE
# ---------------------------------------------------

def clear_permission_cache():
    """Clears cached permissions when permissions are updated."""
    get_permissions_for_role.cache_clear()
