# employees/helpers.py
from graphql import GraphQLError
from .models import RolePermission


def require_permission(info, permission_name: str, target_employee_id=None):
    """
    Database-driven permission checker with:
    - Admin bypass
    - Allow employees to update themselves without needing employee.update permission
    """

    # --------------------------
    # Extract authenticated user
    # --------------------------
    ctx = info.context
    try:
        user = ctx.get("user") if isinstance(ctx, dict) else getattr(ctx, "user", None)
    except Exception:
        user = getattr(ctx, "user", None)

    if not user:
        raise GraphQLError("Authentication required")

    # --------------------------
    # 1. ADMIN BYPASS
    # --------------------------
    if user.roles.filter(name__iexact="Admin").exists():
        return True

    # --------------------------
    # 2. SELF-UPDATE EXCEPTION
    # --------------------------
    if permission_name == "employee.update" and target_employee_id:
        if str(user.id) == str(target_employee_id):
            return True     # Allow user to update their own account

    # --------------------------
    # 3. NORMAL ROLE-BASED CHECK
    # --------------------------
    roles = user.roles.all()
    if not roles.exists():
        raise GraphQLError("User has no role assigned")

    allowed = RolePermission.objects.filter(
        role__in=roles,
        permission__code=permission_name
    ).exists()

    if not allowed:
        raise GraphQLError(f"Permission denied: {permission_name}")

    return True
