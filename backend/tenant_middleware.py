# backend/tenant_middleware.py

"""
Development middleware that reads the X-Tenant header and
activates the matching tenant schema.

In production, TenantMainMiddleware handles this via subdomains.
In development, React Native sends X-Tenant: <schema_name> because
subdomains don't work reliably with LAN IP addresses.

This middleware runs AFTER TenantMainMiddleware. If the tenant
was already resolved by subdomain (production), it does nothing.
If the request arrived on a bare IP (development), it reads
X-Tenant and activates the correct schema.
"""

from django.db import connection
from django.conf import settings
from django.http import JsonResponse


class XTenantMiddleware:
    """
    Reads the X-Tenant header and switches the PostgreSQL
    search_path to the matching tenant schema.

    Only activates when the current schema is 'public' —
    meaning TenantMainMiddleware did not resolve a tenant
    from the subdomain (i.e. development via bare IP).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "ENABLE_X_TENANT_HEADER", False):
            return self.get_response(request)

        schema_name = request.headers.get("X-Tenant", "").strip()

        # Only intervene if we are still on the public schema
        # and the client has told us which tenant it wants.
        if schema_name and connection.schema_name == "public":
            from tenants.models import Business, Domain

            try:
                # Verify this schema actually exists and is a
                # registered tenant — never trust client input blindly.
                business = Business.objects.get(schema_name=schema_name)

                # Switch the connection to the tenant schema.
                # This mirrors what TenantMainMiddleware does via subdomain.
                connection.set_tenant(business)
                request.tenant = business

            except Business.DoesNotExist:
                return JsonResponse(
                    {"error": f"Tenant '{schema_name}' not found."},
                    status=404,
                )

        return self.get_response(request)
