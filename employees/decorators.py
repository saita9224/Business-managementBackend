# employees/decorators.py

import inspect
from functools import wraps
from asgiref.sync import sync_to_async
from .helpers import require_permission


def permission_required(permission_name: str):
    def decorator(func):

        if inspect.iscoroutinefunction(func):
            # ── Async resolver ─────────────────────────────
            @wraps(func)
            async def wrapper(root, info, *args, **kwargs):
                target_employee_id = kwargs.get("id") or kwargs.get("employee_id")
                await sync_to_async(require_permission)(
                    info,
                    permission_name,
                    target_employee_id,
                )
                return await func(root, info, *args, **kwargs)

        else:
            # ── Sync resolver called from async context ────
            # Strawberry runs all resolvers inside an async
            # event loop so even sync resolvers must use
            # sync_to_async for any DB access.
            @wraps(func)
            async def wrapper(root, info, *args, **kwargs):
                target_employee_id = kwargs.get("id") or kwargs.get("employee_id")
                await sync_to_async(require_permission)(
                    info,
                    permission_name,
                    target_employee_id,
                )
                return await sync_to_async(func)(root, info, *args, **kwargs)

        return wrapper

    return decorator