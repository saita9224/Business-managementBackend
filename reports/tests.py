from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from reports.permissions import PERMISSION_META, PERMISSIONS
from reports.types import (
    CreditExposureItemType,
    PaymentMethodBreakdownType,
    SalesSummaryType,
)


class ReportPermissionTests(SimpleTestCase):
    def test_all_permissions_have_metadata(self):
        self.assertEqual(PERMISSIONS, set(PERMISSION_META))


class ReportTypeTests(SimpleTestCase):
    def test_sales_summary_can_hold_nested_breakdowns(self):
        breakdown = PaymentMethodBreakdownType(
            method="CASH",
            total=Decimal("250.00"),
            count=2,
        )
        summary = SalesSummaryType(
            total_revenue=Decimal("250.00"),
            order_count=2,
            avg_order_value=Decimal("125.00"),
            refund_total=Decimal("0.00"),
            credit_total=Decimal("0.00"),
            net_revenue=Decimal("250.00"),
            payment_breakdown=[breakdown],
            daily_breakdown=[],
        )

        self.assertEqual(summary.payment_breakdown[0].method, "CASH")
        self.assertEqual(summary.net_revenue, Decimal("250.00"))

    def test_credit_exposure_item_tracks_overdue_state(self):
        item = CreditExposureItemType(
            receipt_number="RCP-1",
            customer_name="Jane",
            customer_phone=None,
            credit_amount=Decimal("100.00"),
            due_date=date(2026, 5, 1),
            is_overdue=True,
        )

        self.assertTrue(item.is_overdue)
