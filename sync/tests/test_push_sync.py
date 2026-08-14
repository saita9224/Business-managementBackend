# sync/tests/test_push_sync.py

import uuid
from types import SimpleNamespace
import pytest

from sync.types import (
    SyncMutationTypeEnum,
    SyncMutationInput,
    SyncStatusEnum,
)
from sync.mutations import _process_single_sync_item, _process_sync_batch
from sync.registry import SYNC_MUTATION_REGISTRY


def test_sync_registry_coverage():
    """Ensure all mutation enum types are registered with permission and handler."""
    for item in SyncMutationTypeEnum:
        assert item in SYNC_MUTATION_REGISTRY
        assert "permission" in SYNC_MUTATION_REGISTRY[item]
        assert "handler" in SYNC_MUTATION_REGISTRY[item]


def test_sync_item_unsupported_mutation():
    info = SimpleNamespace(context=SimpleNamespace(user=None))
    invalid_input = SimpleNamespace(
        client_id=str(uuid.uuid4()),
        mutation_type="UNSUPPORTED_TYPE",
        payload={},
    )
    result = _process_single_sync_item(info, invalid_input)
    assert result.status == SyncStatusEnum.VALIDATION_ERROR
    assert "Unsupported mutation type" in result.error
