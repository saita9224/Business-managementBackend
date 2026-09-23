# tenants/queries.py

import strawberry
from typing import Optional
from strawberry.types import Info
from asgiref.sync import sync_to_async
from django.db import connection

from tenants.models import Business
from tenants.types import BusinessType


def _get_current_business(info: Info) -> Optional[Business]:
    # 1. Check info.context.tenant
    tenant = getattr(info.context, "tenant", None)
    
    # 2. Check request.tenant
    request = getattr(info.context, "request", None)
    if not tenant and request:
        tenant = getattr(request, "tenant", None)
        
    # 3. Check connection.tenant
    if not tenant:
        tenant = getattr(connection, "tenant", None)

    if isinstance(tenant, Business) and tenant.schema_name != "public":
        return tenant

    return None


@strawberry.type
class TenantQuery:

    @strawberry.field
    async def business(self, info: Info) -> Optional[BusinessType]:
        """
        Returns the Business details for the current active tenant schema.
        """
        b = await sync_to_async(_get_current_business)(info)
        if not b:
            return None

        obj = BusinessType(
            id=b.id,
            name=b.name,
            schema_name=b.schema_name,
            created_at=b.created_at,
        )
        obj._db_instance = b
        return obj
