# employees/decorators.py (fixed)
import inspect
from functools import wraps
from graphql import GraphQLError
from .helpers import require_permission

def permission_required(permission_name: str):
    def decorator(func):
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def wrapper(root, info, *args, **kwargs):
                require_permission(info, permission_name)
                return await func(root, info, *args, **kwargs)
            return wrapper
        else:
            @wraps(func)
            def wrapper(root, info, *args, **kwargs):
                require_permission(info, permission_name)
                return func(root, info, *args, **kwargs)
            return wrapper
    return decorator
