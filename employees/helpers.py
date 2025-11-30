# employees/helpers.py (fixed)
from graphql import GraphQLError
from .models import RolePermission

def require_permission(info, permission_name: str):
    """
    Database-driven permission checker.
    Raises GraphQLError if not allowed.
    """
    user = None
    # support both dict-like and attr contexts
    ctx = info.context
    try:
        user = ctx.get("user") if isinstance(ctx, dict) else getattr(ctx, "user", None)
    except Exception:
        user = getattr(info.context, "user", None)

    if not user:
        raise GraphQLError("Authentication required.")

    # fetch roles (Django queryset)
    roles = user.roles.all()
    if not roles.exists():
        raise GraphQLError("User has no role assigned.")

    # efficient DB check: does any RolePermission exist?
    allowed = RolePermission.objects.filter(
        role__in=roles,
        permission__code=permission_name
    ).exists()

    if not allowed:
        raise GraphQLError(f"Permission denied: {permission_name}")

    return True
