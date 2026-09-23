# tenants/types.py

import strawberry
from typing import Optional
from datetime import datetime
from strawberry.types import Info
from strawberry import Private


@strawberry.type
class BusinessType:
    id: int
    name: str
    schema_name: str
    created_at: datetime
    _db_instance: Private[object] = None

    @strawberry.field
    def logo(self, info: Info) -> Optional[str]:
        """
        Returns relative or absolute media URL for the business logo.
        Nginx serves files from /media/ on the VPS.
        """
        b = self._db_instance
        if b is None:
            return None

        if b.logo and hasattr(b.logo, 'url'):
            url = b.logo.url
            request = getattr(info.context, 'request', None) if info else None
            if request:
                return request.build_absolute_uri(url)
            return url
        return None
