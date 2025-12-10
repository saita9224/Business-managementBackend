# expenses/tests.py

from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model

from expenses.models import Supplier, ExpenseItem, ExpensePayment
from expenses.services import (
    create_supplier,
    update_supplier,
    delete_supplier,
    create_expense_item,
    record_payment,
)

from inventory.models import Product

from strawberry.django.test.client import SchemaTestClient
from backend.schema import schema   # adjust if your schema is in another location


User = get_user_model()


# ------------------------------------------------------------
#                   DATABASE TESTS
# ------------------------------------------------------------

class ExpenseModelTests(TestCase):

    def setUp(self):
        self.supplier = Supplier.objects.create(name="Farmer John")
        self.product = Product.objects.create(name="Maize", price=100)

    def test_expense_item_total_price_calculated(self):
        item = ExpenseItem.objects.create(
            supplier=self.supplier,
            product=self.product,
            item_name="Maize",
            quantity=Decimal("3.5"),
            unit_price=Decimal("100"),
            total_price=0,   # auto-calculated
        )
        self.assertEqual(item.total_price, Decimal("350.00"))

    def test_auto_fill_item_name_from_product(self):
        item = ExpenseItem.objects.create(
            supplier=self.supplier,
            product=self.product,
            item_name="",
            quantity=1,
            unit_price=100,
            total_price=0,
        )
        self.assertEqual(item.item_name, "Maize")

    def test_invalid_quantity_raises_error(self):
        item = ExpenseItem(
            supplier=self.supplier,
            item_name="Bad Item",
            quantity=0,
            unit_price=50,
            total_price=0
        )
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_invalid_unit_price_raises_error(self):
        item = ExpenseItem(
            supplier=self.supplier,
            item_name="Bad Item",
            quantity=1,
            unit_price=0,
            total_price=0
        )
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_amount_paid_and_balance(self):
        item = ExpenseItem.objects.create(
            supplier=self.supplier,
            item_name="Maize",
            quantity=5,
            unit_price=100,
            total_price=500,
        )
        ExpensePayment.objects.create(expense=item, amount=200)

        self.assertEqual(item.amount_paid, Decimal("200.00"))
        self.assertEqual(item.balance, Decimal("300.00"))
        self.assertFalse(item.is_fully_paid)


class ExpensePaymentTests(TestCase):

    def setUp(self):
        self.supplier = Supplier.objects.create(name="Farmer John")
        self.item = ExpenseItem.objects.create(
            supplier=self.supplier,
            item_name="Beans",
            quantity=2,
            unit_price=Decimal("150"),
            total_price=Decimal("300.00"),
        )

    def test_valid_payment(self):
        p = ExpensePayment.objects.create(expense=self.item, amount=Decimal("100"))
        self.assertEqual(p.amount, Decimal("100"))

    def test_reject_zero_payment(self):
        with self.assertRaises(ValidationError):
            p = ExpensePayment(expense=self.item, amount=0)
            p.full_clean()

    def test_reject_overpayment(self):
        ExpensePayment.objects.create(expense=self.item, amount=250)
        with self.assertRaises(ValidationError):
            p = ExpensePayment(expense=self.item, amount=100)
            p.full_clean()


# ------------------------------------------------------------
#                   SERVICE LAYER TESTS
# ------------------------------------------------------------

class ExpenseServiceTests(TestCase):

    def setUp(self):
        self.supplier = create_supplier("Farmer John")
        self.product = Product.objects.create(name="Beans", price=50)

    def test_create_expense_item(self):
        item = create_expense_item(
            supplier_id=self.supplier.id,
            product_id=self.product.id,
            item_name="",
            unit_price=50,
            quantity=2,
        )
        self.assertEqual(item.total_price, Decimal("100.00"))
        self.assertEqual(item.item_name, "Beans")

    def test_record_payment_success(self):
        item = create_expense_item(
            self.supplier.id, self.product.id,
            "Beans", 100, 3
        )  # total = 300

        result = record_payment(item.id, Decimal("150"))
        self.assertEqual(result["expense"].amount_paid, Decimal("150.00"))

    def test_record_payment_reject_overpay(self):
        item = create_expense_item(
            self.supplier.id, self.product.id,
            "Beans", 100, 3
        )  # total = 300
        
        with self.assertRaises(ValidationError):
            record_payment(item.id, Decimal("400"))


# ------------------------------------------------------------
#                   GRAPHQL TESTS
# ------------------------------------------------------------

class ExpenseGraphQLTests(TestCase):

    def setUp(self):
        self.client = SchemaTestClient(schema)

        self.user = User.objects.create_user(
            email="admin@example.com",
            password="Admin123!"
        )
        self.user.permissions = ["expenses.create", "expenses.view", "expenses.pay", "expenses.manage_suppliers"]
        self.user.save()

        self.client.force_login(self.user)

        self.supplier = Supplier.objects.create(name="Test Supplier")

    def test_create_supplier_mutation(self):
        query = """
        mutation {
          createSupplier(name: "AAA") {
            id
            name
          }
        }
        """
        result = self.client.query(query)
        self.assertIsNone(result.errors)
        self.assertEqual(result.data["createSupplier"]["name"], "AAA")

    def test_create_expense_mutation(self):
        query = """
        mutation {
          createExpense(data: {
            supplierId: %d,
            itemName: "Beans",
            price: 100,
            quantity: 2
          }) {
            itemName
            totalPrice
          }
        }
        """ % self.supplier.id

        result = self.client.query(query)
        self.assertIsNone(result.errors)
        self.assertEqual(result.data["createExpense"]["totalPrice"], "200.00")

    def test_pay_balance_mutation(self):
        # create expense first
        item = ExpenseItem.objects.create(
            supplier=self.supplier,
            item_name="Rice",
            quantity=5,
            unit_price=100,
            total_price=500,
        )

        query = """
        mutation {
          payBalance(data: {
            expenseId: %d,
            amount: 200
          }) {
            id
          }
        }
        """ % item.id

        result = self.client.query(query)
        self.assertIsNone(result.errors)

        item.refresh_from_db()
        self.assertEqual(item.amount_paid, Decimal("200.00"))


# ------------------------------------------------------------
#                   DATA LOADER TEST
# ------------------------------------------------------------

class DataloaderTests(TestCase):

    def test_loaders_import(self):
        from expenses.dataloaders import load_suppliers
        self.assertTrue(callable(load_suppliers))

