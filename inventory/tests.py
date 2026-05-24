from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from inventory.models import StockMovement
from inventory.permissions import PERMISSION_META, PERMISSIONS
from inventory.services import remove_stock


class InventoryPermissionTests(SimpleTestCase):
    def test_all_permissions_have_metadata(self):
        self.assertEqual(PERMISSIONS, set(PERMISSION_META))


class InventoryStockValidationTests(SimpleTestCase):
    def test_remove_stock_rejects_invalid_reason_before_writing(self):
        product = type("ProductStub", (), {"current_stock": 10})()
        user = object()

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

        with self.assertRaisesMessage(ValidationError, "Insufficient stock"):
            remove_stock.__wrapped__(
                product=product,
                quantity=2,
                reason=StockMovement.SALE,
                performed_by=user,
            )
