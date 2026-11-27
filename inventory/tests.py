from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from inventory.models import StockMovement, StockMovementReason
from inventory.permissions import PERMISSION_META, PERMISSIONS
from inventory.services import remove_stock


def _reason_stub(**overrides):
    defaults = {
        "is_active": True,
        "code": "SALE",
        "applies_to_out": True,
    }
    defaults.update(overrides)
    return MagicMock(**defaults)


def _patched_reasons(get_return=None, get_side_effect=None):
    """
    Patch inventory.services.StockMovementReason so _validate_reason
    doesn't hit the database. Must be a real class (not a MagicMock)
    because services.py calls isinstance(reason, StockMovementReason).
    """
    class _FakeReason:
        DoesNotExist = StockMovementReason.DoesNotExist
        objects = MagicMock()

    _FakeReason.objects.get.return_value = get_return
    if get_side_effect is not None:
        _FakeReason.objects.get.side_effect = get_side_effect
    return patch("inventory.services.StockMovementReason", _FakeReason)


class InventoryPermissionTests(SimpleTestCase):
    def test_all_permissions_have_metadata(self):
        self.assertEqual(PERMISSIONS, set(PERMISSION_META))


class InventoryStockValidationTests(SimpleTestCase):
    def test_remove_stock_rejects_invalid_reason_before_writing(self):
        product = type("ProductStub", (), {"current_stock": 10})()
        user = object()

        with _patched_reasons(
            get_side_effect=StockMovementReason.DoesNotExist
        ):
            with self.assertRaisesMessage(ValidationError, "Invalid stock reason"):
                remove_stock.__wrapped__(
                    product=product,
                    quantity=1,
                    reason="NOT_A_REASON",
                    performed_by=user,
                )

    def test_remove_stock_rejects_insufficient_stock_before_writing(self):
        product = type("ProductStub", (), {"current_stock": 1})()
        user = object()

        with _patched_reasons(get_return=_reason_stub()):
            with self.assertRaisesMessage(ValidationError, "Insufficient stock"):
                remove_stock.__wrapped__(
                    product=product,
                    quantity=2,
                    reason=StockMovement.SALE,
                    performed_by=user,
                )
