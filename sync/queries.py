# sync/queries.py

from typing import Optional
import strawberry
from strawberry.types import Info
from strawberry.exceptions import GraphQLError
from asgiref.sync import sync_to_async

from .types import PullSyncResponse
from .pull import extract_pull_changes


@strawberry.type
class SyncQuery:

    @strawberry.field
    async def pullChanges(
        self,
        info: Info,
        lastPulledAt: Optional[float] = None,
        schemaVersion: int = 1,
    ) -> PullSyncResponse:
        user = getattr(info.context, "user", None)
        if not user or not user.is_authenticated:
            raise GraphQLError("Authentication required")

        result = await sync_to_async(extract_pull_changes)(lastPulledAt)
        return PullSyncResponse(
            changes=result["changes"],
            timestamp=result["timestamp"],
        )
