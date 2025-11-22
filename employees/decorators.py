# employees/decorators.py

import inspect
from functools import wraps
from graphql import GraphQLError
from .permissions import get_permissions_for_role


def permission_required(permission_name: str):

    def decorator(func):

        if inspect.iscoroutinefunction(func):
            # ASYNC version
            @wraps(func)
            async def async_wrapper(root, info, *args, **kwargs):

                user = info.context.get("user")

                if not user:
                    raise GraphQLError("Authentication required.")

                if not user.role:
                    raise GraphQLError("User has no role assigned.")

                role_permissions = get_permissions_for_role(user.role.name)

                if permission_name not in role_permissions:
                    raise GraphQLError(f"Permission denied: {permission_name}")

                return await func(root, info, *args, **kwargs)

            return async_wrapper

        else:
            # SYNC version
            @wraps(func)
            def sync_wrapper(root, info, *args, **kwargs):

                user = info.context.get("user")

                if not user:
                    raise GraphQLError("Authentication required.")

                if not user.role:
                    raise GraphQLError("User has no role assigned.")

                role_permissions = get_permissions_for_role(user.role.name)

                if permission_name not in role_permissions:
                    raise GraphQLError(f"Permission denied: {permission_name}")

                return func(root, info, *args, **kwargs)

            return sync_wrapper

    return decorator
