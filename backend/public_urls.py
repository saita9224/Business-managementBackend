# backend/public_urls.py
#
# Handles all requests arriving on the bare/public domain —
# i.e. when no tenant subdomain is matched by TenantMainMiddleware.
#
# This file serves:
#   - Social auth (Google/Facebook) — must be public because the
#     user has no tenant subdomain yet when they first sign in
#   - Platform-level Django admin (manages Business + Domain records)
#   - Health check endpoint
#
# Regular tenant GraphQL (inventory, POS, HR, etc.) is NOT here —
# those requests arrive on a subdomain and are handled by backend/urls.py

import strawberry
from django.contrib import admin
from django.urls import path
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from strawberry.django.views import AsyncGraphQLView

from authentication.social_mutations import SocialAuthMutation


# ======================================================
# PUBLIC GRAPHQL SCHEMA
# Minimal — only the mutations needed before a tenant
# context exists. Everything else lives in backend/urls.py
# ======================================================

@strawberry.type
class PublicQuery:
    @strawberry.field
    def status(self) -> str:
        """Health check — confirms the public schema is reachable."""
        return "ok"


@strawberry.type
class PublicMutation(SocialAuthMutation):
    """
    Inherits socialAuth mutation from SocialAuthMutation.
    Add any other pre-auth mutations here in future
    (e.g. check if a business name is available).
    """
    pass


public_schema = strawberry.Schema(
    query=PublicQuery,
    mutation=PublicMutation,
)


# ======================================================
# PUBLIC GRAPHQL VIEW
# No dataloaders, no JWTMiddleware — those belong on the
# tenant endpoint. This view is intentionally minimal.
# ======================================================

class PublicGraphQLView(AsyncGraphQLView):
    """
    Thin wrapper kept in case you need to inject public-schema
    context (e.g. rate limiting, analytics) in future.
    Nothing extra needed right now.
    """
    pass


# ======================================================
# HEALTH CHECK
# ======================================================

def platform_status(request):
    return JsonResponse({
        "status": "ok",
        "message": "Hoppers Business Platform — public schema",
    })


# ======================================================
# URL PATTERNS
# ======================================================

urlpatterns = [
    # Platform-level Django admin.
    # Operates in the public schema — use this to create and
    # manage Business and Domain records (i.e. onboard tenants).
    path("admin/", admin.site.urls),

    # Simple HTTP health check (no GraphQL overhead).
    path("status/", platform_status),

    # Public GraphQL endpoint.
    # Mobile app calls this for socialAuth before it has a subdomain.
    # graphiql=True lets you test mutations in the browser at /auth/
    path(
        "auth/",
        csrf_exempt(
            PublicGraphQLView.as_view(schema=public_schema, graphiql=True)
        ),
    ),
]