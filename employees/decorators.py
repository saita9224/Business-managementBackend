# employees/decorators.py

import inspect
from functools import wraps
from asgiref.sync import sync_to_async
from .helpers import require_permission


def permission_required(permission_name: str):
    def decorator(func):

        if inspect.iscoroutinefunction(func):
            # async resolver
            @wraps(func)
            async def wrapper(root, info, *args, **kwargs):

                target_employee_id = kwargs.get("id") or kwargs.get("employee_id")

                # run sync permission check safely
                await sync_to_async(require_permission)(
                    info,
                    permission_name,
                    target_employee_id,
                )

                return await func(root, info, *args, **kwargs)

            return wrapper

        else:
            # sync resolver
            @wraps(func)
            def wrapper(root, info, *args, **kwargs):

                target_employee_id = kwargs.get("id") or kwargs.get("employee_id")

                require_permission(info, permission_name, target_employee_id)
                return func(root, info, *args, **kwargs)

            return wrapper

    return decorator