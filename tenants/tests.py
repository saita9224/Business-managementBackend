from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from tenants.models import Business, PendingRegistration, SuperAdmin


class TenantModelTests(SimpleTestCase):
    def test_business_string_is_name(self):
        business = Business(name="Demo Hotel")

        self.assertEqual(str(business), "Demo Hotel")

    def test_super_admin_password_helpers_hash_and_verify(self):
        admin = SuperAdmin(email="admin@example.com", name="Admin")

        admin.set_password("Secret123!")

        self.assertNotEqual(admin.password, "Secret123!")
        self.assertTrue(admin.check_password("Secret123!"))
        self.assertFalse(admin.check_password("wrong"))

    def test_pending_registration_expiry_property(self):
        pending = PendingRegistration(
            email="owner@example.com",
            business_name="Demo Hotel",
            pin="123456",
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        self.assertTrue(pending.is_expired)
