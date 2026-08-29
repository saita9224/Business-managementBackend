# sync/tests/test_pull_sync.py

from types import SimpleNamespace
from unittest.mock import patch, MagicMock
import pytest

from sync.pull import extract_pull_changes, _parse_timestamp, serialize_menu_item
from sync.queries import SyncQuery


def test_parse_timestamp():
    assert _parse_timestamp(None) is None
    assert _parse_timestamp(0) is None

    # Test seconds timestamp
    ts_sec = 1755853200.0
    dt_sec = _parse_timestamp(ts_sec)
    assert dt_sec is not None

    # Test milliseconds timestamp
    ts_ms = 1755853200000.0
    dt_ms = _parse_timestamp(ts_ms)
    assert dt_ms is not None
    assert int(dt_sec.timestamp()) == int(dt_ms.timestamp())


@patch("sync.pull.get_table_changes")
def test_extract_pull_changes_structure(mock_get_table_changes):
    mock_get_table_changes.return_value = {
        "created": [],
        "updated": [],
        "deleted": [],
    }

    res = extract_pull_changes(last_pulled_at=None)
    assert "changes" in res
    assert "timestamp" in res
    assert res["timestamp"] > 0

    changes = res["changes"]
    for table in ["products", "categories", "menu_categories", "menu_items", "receipts", "expenses", "stock_movements"]:
        assert table in changes
        assert "created" in changes[table]
        assert "updated" in changes[table]
        assert "deleted" in changes[table]


def test_serialize_menu_item_matches_current_model_fields():
    menu_item = SimpleNamespace(
        id=1,
        name="Tea",
        category="drinks",
        emoji="T",
        price=50,
        product_id=None,
        is_available=True,
        is_pinned=False,
        created_at=None,
        updated_at=None,
    )

    data = serialize_menu_item(menu_item)

    assert data["category"] == "drinks"
    assert data["emoji"] == "T"
    assert data["product_id"] is None
    assert "category_id" not in data
    assert "image_url" not in data


@pytest.mark.anyio
async def test_pull_changes_query_unauthenticated():
    info = SimpleNamespace(context=SimpleNamespace(user=None))
    query_obj = SyncQuery()
    with pytest.raises(Exception) as exc_info:
        await query_obj.pullChanges(info)
    assert "Authentication required" in str(exc_info.value)


@pytest.mark.anyio
@patch("sync.queries.extract_pull_changes")
async def test_pull_changes_query_authenticated(mock_extract):
    mock_extract.return_value = {
        "changes": {"products": {"created": [], "updated": [], "deleted": []}},
        "timestamp": 1755853200000.0,
    }

    mock_user = MagicMock()
    mock_user.is_authenticated = True
    info = SimpleNamespace(context=SimpleNamespace(user=mock_user))

    query_obj = SyncQuery()
    res = await query_obj.pullChanges(info, lastPulledAt=1755853200000.0)
    assert res.timestamp == 1755853200000.0
    assert "products" in res.changes
