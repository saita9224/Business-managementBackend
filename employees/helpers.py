# employees/helpers.py

from graphql import GraphQLError
from .models import Permission, RolePermission, EmployeeRole


def require_permission(info, permission_name: str):
    """
    Database-driven permission checker.

    Use inside resolvers:

        def resolve_all_expenses(root, info):
            require_permission(info, "expenses.view")
            return Expense.objects.all()
    """

    user = info.context.get("user")

    if not user:
        raise GraphQLError("Authentication required.")

    # 1. Get user roles
    roles = user.roles.all()   # because EmployeeRole links user -> Role

    if not roles:
        raise GraphQLError("User has no role assigned.")

    # 2. Check if any role grants the permission
    allowed = RolePermission.objects.filter(
        role__in=roles,
        permission__name=permission_name
    ).exists()

    if not allowed:
        raise GraphQLError(f"Permission denied: {permission_name}")

    return True
