from datetime import timedelta
from django.test import SimpleTestCase, TestCase, RequestFactory
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from unittest.mock import MagicMock, patch

from tenants.models import Business, PendingRegistration, SuperAdmin
from tenants.queries import _get_current_business
from tenants.views import upload_business_logo


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


class TenantQueryHelperTests(SimpleTestCase):
    def test_get_current_business_returns_business_from_context(self):
        biz = Business(name="Test Biz", schema_name="test_schema")
        info = MagicMock()
        info.context.tenant = biz

        result = _get_current_business(info)
        self.assertEqual(result, biz)

    def test_get_current_business_ignores_public_schema(self):
        biz = Business(name="Public", schema_name="public")
        info = MagicMock()
        info.context.tenant = biz

        result = _get_current_business(info)
        self.assertIsNone(result)


class RESTUploadLogoTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()

    async def test_upload_logo_requires_post(self):
        request = self.rf.get("/api/tenants/upload-logo/")
        response = await upload_business_logo(request)
        self.assertEqual(response.status_code, 405)

    async def test_upload_logo_requires_token(self):
        request = self.rf.post("/api/tenants/upload-logo/")
        response = await upload_business_logo(request)
        self.assertEqual(response.status_code, 401)
