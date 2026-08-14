# sync/mutations.py

import logging
from typing import List
import strawberry
from strawberry.types import Info
from strawberry.exceptions import GraphQLError
from asgiref.sync import sync_to_async
from django.db import transaction
from django.core.exceptions import ValidationError

from employees.helpers import require_permission

from .types import (
    SyncMutationInput,
    SyncItemResult,
    PushSyncPayload,
    SyncStatusEnum,
)
from .registry import SYNC_MUTATION_REGISTRY

logger = logging.getLogger(__name__)


def _process_single_sync_item(info: Info, item: SyncMutationInput) -> SyncItemResult:
    entry = SYNC_MUTATION_REGISTRY.get(item.mutation_type)
    if not entry:
        type_str = item.mutation_type.value if hasattr(item.mutation_type, "value") else str(item.mutation_type)
        return SyncItemResult(
            client_id=item.client_id,
            mutation_type=item.mutation_type,
            status=SyncStatusEnum.VALIDATION_ERROR,
            error=f"Unsupported mutation type: {type_str}",
        )

    required_perm = entry["permission"]
    handler = entry["handler"]

    # 1. Item Permission Validation against employee roles
    try:
        require_permission(info, required_perm)
    except GraphQLError as perm_err:
        return SyncItemResult(
            client_id=item.client_id,
            mutation_type=item.mutation_type,
            status=SyncStatusEnum.PERMISSION_DENIED,
            error=str(perm_err),
        )
    except Exception as e:
        return SyncItemResult(
            client_id=item.client_id,
            mutation_type=item.mutation_type,
            status=SyncStatusEnum.PERMISSION_DENIED,
            error=f"Permission check failed: {str(e)}",
        )

    user = info.context.user

    # 2. Item-level atomic transaction for partial success isolation
    try:
        with transaction.atomic():
            created, payload_response = handler(user, item.payload or {}, item.client_id)
            status = (
                SyncStatusEnum.SUCCESS
                if created
                else SyncStatusEnum.DUPLICATE_IGNORED
            )
            return SyncItemResult(
                client_id=item.client_id,
                mutation_type=item.mutation_type,
                status=status,
                payload_response=payload_response,
            )
    except ValidationError as val_err:
        msg = "; ".join(val_err.messages) if hasattr(val_err, "messages") else str(val_err)
        return SyncItemResult(
            client_id=item.client_id,
            mutation_type=item.mutation_type,
            status=SyncStatusEnum.VALIDATION_ERROR,
            error=msg,
        )
    except Exception as exc:
        logger.exception(f"Sync execution failed for client_id {item.client_id}")
        return SyncItemResult(
            client_id=item.client_id,
            mutation_type=item.mutation_type,
            status=SyncStatusEnum.INTERNAL_ERROR,
            error=str(exc),
        )


def _process_sync_batch(info: Info, mutations: List[SyncMutationInput]) -> List[SyncItemResult]:
    results = []
    for item in mutations:
        result = _process_single_sync_item(info, item)
        results.append(result)
    return results


@strawberry.type
class SyncMutation:

    @strawberry.mutation
    async def pushSync(
        self,
        info: Info,
        mutations: List[SyncMutationInput],
    ) -> PushSyncPayload:
        user = getattr(info.context, "user", None)
        if not user or not user.is_authenticated:
            raise GraphQLError("Authentication required")

        results = await sync_to_async(_process_sync_batch)(info, mutations)
        return PushSyncPayload(results=results)
