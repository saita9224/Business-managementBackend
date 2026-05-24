from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from .services import add_menu_order_item


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
