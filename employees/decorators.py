# employees/decorators.py
import inspect
from functools import wraps
from .helpers import require_permission


def permission_required(permission_name: str):
    """
    Decorator that enforces RBAC permissions.
    Now supports passing employee ID for self-update access.
    """
    def decorator(func):

        if inspect.iscoroutinefunction(func):
            # async resolver
            @wraps(func)
            async def wrapper(root, info, *args, **kwargs):

                # Extract employee ID for updateEmployee(id: ...)
                target_employee_id = kwargs.get("id")

                require_permission(info, permission_name, target_employee_id)
                return await func(root, info, *args, **kwargs)

            return wrapper

        else:
            # sync resolver
            @wraps(func)
            def wrapper(root, info, *args, **kwargs):

                # Extract employee ID for updateEmployee(id: ...)
                target_employee_id = kwargs.get("id")

                require_permission(info, permission_name, target_employee_id)
                return func(root, info, *args, **kwargs)

            return wrapper

    return decorator
