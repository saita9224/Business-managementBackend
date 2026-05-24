from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from backend.tenant_middleware import XTenantMiddleware


class XTenantMiddlewareTests(SimpleTestCase):
    @patch("backend.tenant_middleware.connection")
    def test_no_header_leaves_request_untouched(self, connection):
        connection.schema_name = "public"
        get_response = Mock(return_value="response")
        middleware = XTenantMiddleware(get_response)
        request = SimpleNamespace(headers={})

        response = middleware(request)

        self.assertEqual(response, "response")
        self.assertFalse(hasattr(request, "tenant"))
        get_response.assert_called_once_with(request)

    @patch("backend.tenant_middleware.connection")
    def test_header_is_ignored_when_schema_already_tenant(self, connection):
        connection.schema_name = "demo"
        get_response = Mock(return_value="response")
        middleware = XTenantMiddleware(get_response)
        request = SimpleNamespace(headers={"X-Tenant": "other"})

        response = middleware(request)

        self.assertEqual(response, "response")
        connection.set_tenant.assert_not_called()
