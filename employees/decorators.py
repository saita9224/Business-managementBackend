# employees/decorators.py

import inspect
from functools import wraps
from graphql import GraphQLError

from employees.permissions import get_permissions_for_role


def permission_required(permission_name: str):
    """
    Decorator to check if a user (with multiple roles) has the required permission.
    """

    def decorator(func):

        async def _check_async(root, info, *args, **kwargs):
            user = info.context.get("user")

            if not user:
                raise GraphQLError("Authentication required.")

            roles = user.roles.all()
            if not roles:
                raise GraphQLError("User has no roles assigned.")

            # UNION of permissions
            permission_set = set()
            for role in roles:
                for perm in role.permissions.all():
                    permission_set.add(perm.code)

            if permission_name not in permission_set:
                raise GraphQLError(f"Permission denied: {permission_name}")

            return await func(root, info, *args, **kwargs)

        def _check_sync(root, info, *args, **kwargs):
            user = info.context.get("user")

            if not user:
                raise GraphQLError("Authentication required.")

            roles = user.roles.all()
            if not roles:
                raise GraphQLError("User has no roles assigned.")

            # UNION of permissions
            permission_set = set()
            for role in roles:
                for perm in role.permissions.all():
                    permission_set.add(perm.code)

            if permission_name not in permission_set:
                raise GraphQLError(f"Permission denied: {permission_name}")

            return func(root, info, *args, **kwargs)

        # Choose SYNC / ASYNC based on resolver
        if inspect.iscoroutinefunction(func):
            return wraps(func)(_check_async)
        else:
            return wraps(func)(_check_sync)

    return decorator
