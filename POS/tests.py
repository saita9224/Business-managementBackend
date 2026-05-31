from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from .models import Receipt
from .services import add_menu_order_item, delete_draft_receipt


class POSMenuOrderItemTests(SimpleTestCase):
    @patch("POS.services._get_or_create_default_price_list")
    @patch("POS.services.OrderItem")
    def test_linked_menu_item_keeps_inventory_product_id(
        self,
        order_item_cls,
        get_price_list,
    ):
        get_price_list.return_value = object()

        def make_order_item(**kwargs):
            item = SimpleNamespace(**kwargs)
            item.full_clean = Mock()
            item.save = Mock()
            return item

        order_item_cls.side_effect = make_order_item
        menu_item = SimpleNamespace(
            product_id=123,
            name="Test Soda",
            price=Decimal("100.00"),
        )

        item = add_menu_order_item.__wrapped__(
            order=object(),
            menu_item=menu_item,
            quantity=2,
            sold_by=object(),
        )

        self.assertEqual(item.product_id, 123)
        self.assertEqual(item.line_total, Decimal("200.00"))

    @patch("POS.services._get_or_create_default_price_list")
    @patch("POS.services.OrderItem")
    def test_manual_menu_item_uses_zero_product_id(
        self,
        order_item_cls,
        get_price_list,
    ):
        get_price_list.return_value = object()

        def make_order_item(**kwargs):
            item = SimpleNamespace(**kwargs)
            item.full_clean = Mock()
            item.save = Mock()
            return item

        order_item_cls.side_effect = make_order_item
        menu_item = SimpleNamespace(
            product_id=None,
            name="Manual Service",
            price=Decimal("50.00"),
        )

        item = add_menu_order_item.__wrapped__(
            order=object(),
            menu_item=menu_item,
            quantity=1,
            sold_by=object(),
        )

        self.assertEqual(item.product_id, 0)


class POSDeleteDraftReceiptTests(SimpleTestCase):
    @patch("POS.services.CreditAccount")
    @patch("POS.services.Receipt.objects")
    def test_delete_draft_receipt_deletes_safe_draft(
        self,
        receipt_objects,
        credit_account_cls,
    ):
        receipt = SimpleNamespace(
            created_by_id=1,
            status=Receipt.DRAFT,
            submitted_at=None,
            payments=SimpleNamespace(exists=Mock(return_value=False)),
            delete=Mock(),
        )
        receipt_objects.select_for_update.return_value.get.return_value = receipt
        credit_account_cls.objects.filter.return_value.exists.return_value = False

        result = delete_draft_receipt.__wrapped__(
            receipt_id=10,
            deleted_by=SimpleNamespace(id=1, is_superuser=False),
        )

        self.assertTrue(result)
        receipt.delete.assert_called_once_with()

    @patch("POS.services.CreditAccount")
    @patch("POS.services.Receipt.objects")
    def test_delete_draft_receipt_rejects_non_draft(
        self,
        receipt_objects,
        credit_account_cls,
    ):
        receipt = SimpleNamespace(
            created_by_id=1,
            status=Receipt.PENDING,
            submitted_at=None,
            payments=SimpleNamespace(exists=Mock(return_value=False)),
            delete=Mock(),
        )
        receipt_objects.select_for_update.return_value.get.return_value = receipt
        credit_account_cls.objects.filter.return_value.exists.return_value = False

        with self.assertRaisesMessage(ValidationError, "Only draft receipts"):
            delete_draft_receipt.__wrapped__(
                receipt_id=10,
                deleted_by=SimpleNamespace(id=1, is_superuser=False),
            )

        receipt.delete.assert_not_called()

    @patch("POS.services.Receipt.objects")
    def test_delete_draft_receipt_rejects_other_users_draft(self, receipt_objects):
        receipt = SimpleNamespace(
            created_by_id=1,
            status=Receipt.DRAFT,
            submitted_at=None,
            payments=SimpleNamespace(exists=Mock(return_value=False)),
            delete=Mock(),
        )
        receipt_objects.select_for_update.return_value.get.return_value = receipt

        with self.assertRaisesMessage(ValidationError, "your own draft"):
            delete_draft_receipt.__wrapped__(
                receipt_id=10,
                deleted_by=SimpleNamespace(id=2, is_superuser=False),
            )

        receipt.delete.assert_not_called()
