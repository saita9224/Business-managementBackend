# expenses/permissions.py

import inspect
from functools import wraps
from graphql import GraphQLError

# ────────────────────────────────────────────────
#  SOURCE-OF-TRUTH PERMISSIONS FOR EXPENSES APP
# ────────────────────────────────────────────────
# These are inserted into the DB by the global loader.
#
# Pattern: "expenses.action"
# Example: "expenses.create", "expenses.pay", etc.
# ────────────────────────────────────────────────

EXPENSE_PERMISSIONS = [
    # CRUD on Expense Items
    "expenses.create",
    "expenses.update",
    "expenses.delete",
    "expenses.view",

    # Payments
    "expenses.pay",
    "expenses.view_payments",

    # Supplier management
    "expenses.manage_suppliers",
]


# ────────────────────────────────────────────────
#  DECORATOR: expense_permission_required()
# ────────────────────────────────────────────────
# Works for async & sync resolvers.
# Same architecture as employees.permissions
# ────────────────────────────────────────────────

def expense_permission_required(permission_name: str):

    def decorator(func):

        # Handle ASYNC resolvers
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(root, info, *args, **kwargs):
                user = info.context.request.user

                if not user.is_authenticated:
                    raise GraphQLError("Authentication required.")

                if not user.has_permission(permission_name):
                    raise GraphQLError("Permission denied: " + permission_name)

                return await func(root, info, *args, **kwargs)
            return async_wrapper

        # Handle SYNC resolvers
        @wraps(func)
        def sync_wrapper(root, info, *args, **kwargs):
            user = info.context.request.user

            if not user.is_authenticated:
                raise GraphQLError("Authentication required.")

            if not user.has_permission(permission_name):
                raise GraphQLError("Permission denied: " + permission_name)

            return func(root, info, *args, **kwargs)

        return sync_wrapper

    return decorator
