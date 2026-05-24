from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from expenses.models import ExpenseItem, Supplier
from expenses.permissions import PERMISSION_META, PERMISSIONS
from expenses.utils import to_decimal


class ExpensesUtilityTests(SimpleTestCase):
    def test_to_decimal_accepts_numeric_strings(self):
        self.assertEqual(to_decimal("12.50", "amount"), Decimal("12.50"))

    def test_to_decimal_rejects_invalid_values(self):
        with self.assertRaises(ValidationError):
            to_decimal("not-a-number", "amount")


class ExpenseItemValidationTests(SimpleTestCase):
    def test_clean_calculates_total_price(self):
        item = ExpenseItem(
            supplier=Supplier(name="Farmer John"),
            item_name="Beans",
            quantity=Decimal("2.500"),
            unit_price=Decimal("40.00"),
        )

        item.clean()

        self.assertEqual(item.total_price, Decimal("100.00"))

    def test_clean_rejects_zero_quantity(self):
        item = ExpenseItem(
            item_name="Beans",
            quantity=Decimal("0"),
            unit_price=Decimal("40.00"),
        )

        with self.assertRaises(ValidationError):
            item.clean()


class ExpensePermissionTests(SimpleTestCase):
    def test_all_permissions_have_metadata(self):
        self.assertEqual(PERMISSIONS, set(PERMISSION_META))
