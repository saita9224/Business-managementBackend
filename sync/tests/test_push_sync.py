# sync/tests/test_push_sync.py

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sync.types import (
    SyncMutationTypeEnum,
    SyncStatusEnum,
)
from sync.mutations import _process_single_sync_item, _process_sync_batch
from sync.registry import SYNC_MUTATION_REGISTRY
from sync.handlers import handle_add_order_item, handle_accept_payment


class DummyAtomic:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


def test_sync_registry_coverage():
    """Ensure all mutation enum types are registered with permission and handler."""
    for item in SyncMutationTypeEnum:
        assert item in SYNC_MUTATION_REGISTRY
        assert "permission" in SYNC_MUTATION_REGISTRY[item]
        assert "handler" in SYNC_MUTATION_REGISTRY[item]


def test_accept_payment_sync_uses_payment_permission():
    assert (
        SYNC_MUTATION_REGISTRY[SyncMutationTypeEnum.ACCEPT_PAYMENT]["permission"]
        == "pos.accept_payment"
    )


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


def test_sync_item_permission_denied():
    mock_user = MagicMock()
    mock_user.is_active = True
    mock_user.roles.filter.return_value.exists.return_value = False
    mock_user.roles.all.return_value.exists.return_value = False

    info = SimpleNamespace(context=SimpleNamespace(user=mock_user))
    item = SimpleNamespace(
        client_id=str(uuid.uuid4()),
        mutation_type=SyncMutationTypeEnum.CREATE_RECEIPT,
        payload={"session_id": 1},
    )

    result = _process_single_sync_item(info, item)
    assert result.status == SyncStatusEnum.PERMISSION_DENIED
    assert "User has no role assigned" in result.error


@patch("sync.mutations.transaction.atomic", return_value=DummyAtomic())
def test_sync_item_success_handler_dispatch(mock_atomic):
    mock_user = MagicMock()
    mock_user.is_active = True
    mock_user.roles.filter.return_value.exists.return_value = True  # Admin bypass

    client_id = str(uuid.uuid4())
    info = SimpleNamespace(context=SimpleNamespace(user=mock_user))
    item = SimpleNamespace(
        client_id=client_id,
        mutation_type=SyncMutationTypeEnum.CREATE_RECEIPT,
        payload={"session_id": 1},
    )

    dummy_response = {"receipt_id": 100, "receipt_number": "RCP-0001", "status": "DRAFT"}
    mock_handler = MagicMock(return_value=(True, dummy_response))

    with patch.dict("sync.mutations.SYNC_MUTATION_REGISTRY", {
        SyncMutationTypeEnum.CREATE_RECEIPT: {
            "permission": "pos.create_order",
            "handler": mock_handler,
        }
    }):
        result = _process_single_sync_item(info, item)

    assert result.status == SyncStatusEnum.SUCCESS
    assert result.client_id == client_id
    assert result.payload_response == dummy_response


@patch("sync.mutations.transaction.atomic", return_value=DummyAtomic())
def test_sync_item_duplicate_ignored(mock_atomic):
    mock_user = MagicMock()
    mock_user.is_active = True
    mock_user.roles.filter.return_value.exists.return_value = True  # Admin bypass

    client_id = str(uuid.uuid4())
    info = SimpleNamespace(context=SimpleNamespace(user=mock_user))
    item = SimpleNamespace(
        client_id=client_id,
        mutation_type=SyncMutationTypeEnum.CREATE_RECEIPT,
        payload={"session_id": 1},
    )

    dummy_response = {"receipt_id": 100, "receipt_number": "RCP-0001", "status": "DRAFT"}
    mock_handler = MagicMock(return_value=(False, dummy_response))

    with patch.dict("sync.mutations.SYNC_MUTATION_REGISTRY", {
        SyncMutationTypeEnum.CREATE_RECEIPT: {
            "permission": "pos.create_order",
            "handler": mock_handler,
        }
    }):
        result = _process_single_sync_item(info, item)

    assert result.status == SyncStatusEnum.DUPLICATE_IGNORED
    assert result.client_id == client_id


@patch("sync.mutations.transaction.atomic", return_value=DummyAtomic())
def test_sync_batch_processing(mock_atomic):
    mock_user = MagicMock()
    mock_user.is_active = True
    mock_user.roles.filter.return_value.exists.return_value = True

    info = SimpleNamespace(context=SimpleNamespace(user=mock_user))
    item1 = SimpleNamespace(
        client_id=str(uuid.uuid4()),
        mutation_type=SyncMutationTypeEnum.CREATE_RECEIPT,
        payload={"session_id": 1},
    )
    item2 = SimpleNamespace(
        client_id=str(uuid.uuid4()),
        mutation_type=SyncMutationTypeEnum.CREATE_ORDER,
        payload={"receipt_id": 100},
    )

    mock_h1 = MagicMock(return_value=(True, {"receipt_id": 1}))
    mock_h2 = MagicMock(return_value=(False, {"order_id": 2}))

    with patch.dict("sync.mutations.SYNC_MUTATION_REGISTRY", {
        SyncMutationTypeEnum.CREATE_RECEIPT: {"permission": "pos.create_order", "handler": mock_h1},
        SyncMutationTypeEnum.CREATE_ORDER: {"permission": "pos.create_order", "handler": mock_h2},
    }):
        results = _process_sync_batch(info, [item1, item2])

    assert len(results) == 2
    assert results[0].status == SyncStatusEnum.SUCCESS
    assert results[1].status == SyncStatusEnum.DUPLICATE_IGNORED


@patch("sync.handlers.OrderItem")
def test_add_order_item_duplicate_replay_returns_existing(mock_order_item):
    existing = MagicMock()
    existing.id = 10
    existing.order_id = 20
    existing.line_total = "30.00"
    mock_order_item.objects.filter.return_value.first.return_value = existing

    created, payload = handle_add_order_item(
        MagicMock(),
        {"order_id": 20, "product_id": 1},
        str(uuid.uuid4()),
    )

    assert created is False
    assert payload["order_item_id"] == 10


@patch("sync.handlers.Payment")
def test_accept_payment_duplicate_replay_returns_existing(mock_payment):
    existing = MagicMock()
    existing.id = 10
    existing.receipt_id = 20
    existing.amount = "30.00"
    mock_payment.objects.filter.return_value.first.return_value = existing

    created, payload = handle_accept_payment(
        MagicMock(),
        {"receipt_id": 20, "amount": 30, "method": "CASH"},
        str(uuid.uuid4()),
    )

    assert created is False
    assert payload["payment_id"] == 10
