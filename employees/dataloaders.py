# employees/dataloaders.py

from collections import defaultdict
from typing import List

from asgiref.sync import sync_to_async
from strawberry.dataloader import DataLoader

from .models import RolePermission


# ======================================================
# PERMISSIONS BY ROLE
# Batches RoleType.permissions lookups — one query for
# all roles in a request instead of one per role.
# ======================================================

async def load_permissions_by_role(keys: List[int]):
    links = await sync_to_async(list)(
        RolePermission.objects
        .filter(role_id__in=keys)
        .select_related("permission")
    )

    grouped = defaultdict(list)
    for link in links:
        grouped[link.role_id].append(link.permission)

    return [grouped.get(k, []) for k in keys]


def create_employees_dataloaders() -> dict:
    """Request-scoped loaders — must be created per request."""
    return {
        "permissions_by_role_loader":
            DataLoader(load_fn=load_permissions_by_role),
    }
