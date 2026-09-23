# tenants/mutations.py

import strawberry
from typing import Optional
from strawberry.types import Info
from strawberry.file_uploads import Upload
from graphql import GraphQLError
from asgiref.sync import sync_to_async

from tenants.models import Business
from tenants.types import BusinessType
from tenants.queries import _get_current_business
from tenants.services import update_business_logo as save_business_logo
from tenants.services import update_business_name
from employees.decorators import permission_required


@strawberry.type
class TenantMutation:

    @strawberry.mutation
    @permission_required("tenant.manage_profile")
    async def update_business_logo(
        self, info: Info, logo: Upload
    ) -> BusinessType:
        """
        Uploads and updates the current business logo image.
        Nginx serves the uploaded image directly via /media/ logos.
        """
        b = await sync_to_async(_get_current_business)(info)
        if not b:
            raise GraphQLError("No active business found for this tenant domain/header.")

        try:
            updated_b = await sync_to_async(save_business_logo)(b.id, logo)
        except ValueError as exc:
            raise GraphQLError(str(exc))

        obj = BusinessType(
            id=updated_b.id,
            name=updated_b.name,
            schema_name=updated_b.schema_name,
            created_at=updated_b.created_at,
        )
        obj._db_instance = updated_b
        return obj

    @strawberry.mutation
    @permission_required("tenant.manage_profile")
    async def update_business_profile(
        self, info: Info, name: Optional[str] = None
    ) -> BusinessType:
        """
        Updates the business profile details (e.g. business name).
        """
        b = await sync_to_async(_get_current_business)(info)
        if not b:
            raise GraphQLError("No active business found for this tenant domain/header.")

        if name and name.strip():
            try:
                b = await sync_to_async(update_business_name)(b.id, name.strip())
            except ValueError as exc:
                raise GraphQLError(str(exc))

        obj = BusinessType(
            id=b.id,
            name=b.name,
            schema_name=b.schema_name,
            created_at=b.created_at,
        )
        obj._db_instance = b
        return obj
