# backend/public_urls.py
#
# Handles all requests arriving on the bare/public domain —
# i.e. when no tenant subdomain is matched by TenantMainMiddleware.
#
# This file serves:
#   - Google OAuth (googleAuth mutation)
#   - Email+password admin registration (requestRegistration,
#     verifyRegistration mutations)
#   - SuperAdmin login and management (separate endpoint)
#   - Platform-level Django admin
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
from authentication.mutations import AuthMutation


# ======================================================
# PUBLIC GRAPHQL SCHEMA
# Contains every mutation needed before a tenant context
# exists. Everything else lives in backend/urls.py.
# ======================================================

@strawberry.type
class PublicQuery:
    @strawberry.field
    def status(self) -> str:
        """Health check — confirms the public schema is reachable."""
        return "ok"


@strawberry.type
class PublicMutation(SocialAuthMutation, AuthMutation):
    """
    Combines:
      SocialAuthMutation → googleAuth
      AuthMutation       → login, requestRegistration, verifyRegistration

    All pre-auth mutations live here so the mobile app has a single
    public endpoint to call before it has a tenant subdomain.
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
# SUPER ADMIN SCHEMA
# Completely separate from the public schema.
# SuperAdmin is not an Employee — it is a platform-level
# account that lives in the public schema and can reach
# into any tenant schema via schema_context.
# ======================================================

@strawberry.type
class SuperAdminQuery:
    @strawberry.field
    def super_status(self) -> str:
        """Health check for the SuperAdmin endpoint."""
        return "SuperAdmin endpoint active"


@strawberry.type
class SuperAdminMutation:

    @strawberry.mutation
    async def super_admin_login(
        self,
        email:    str,
        password: str,
    ) -> "SuperAdminLoginPayload":
        """
        Authenticate the platform SuperAdmin.
        Returns a SuperAdmin JWT — distinct from employee JWTs,
        contains role='superadmin' and no schema_name.
        """
        from asgiref.sync import sync_to_async
        from django.utils import timezone
        from tenants.models import SuperAdmin
        from authentication.services import create_super_admin_jwt
        from graphql import GraphQLError

        def _authenticate(email: str, password: str):
            try:
                sa = SuperAdmin.objects.get(
                    email__iexact=email,
                    is_active=True,
                )
                if not sa.check_password(password):
                    return None
                sa.last_login = timezone.now()
                sa.save(update_fields=["last_login"])
                return sa
            except SuperAdmin.DoesNotExist:
                return None

        sa = await sync_to_async(_authenticate)(email, password)

        if not sa:
            raise GraphQLError("Invalid credentials")

        token = create_super_admin_jwt(sa)

        return SuperAdminLoginPayload(
            token=    token,
            admin_id= sa.id,
            name=     sa.name,
            email=    sa.email,
        )

    @strawberry.mutation
    async def list_tenants(self, info) -> list[str]:
        """
        List all registered tenant names.
        Requires a valid SuperAdmin JWT in the Authorization header.
        Add further SuperAdmin mutations here as needed.
        """
        from asgiref.sync import sync_to_async
        from tenants.models import Business
        from authentication.services import decode_super_admin_jwt
        from graphql import GraphQLError

        token = _extract_bearer_token(info)
        if not token:
            raise GraphQLError("SuperAdmin authentication required")

        sa = await decode_super_admin_jwt(token)
        if not sa:
            raise GraphQLError("Invalid or expired SuperAdmin token")

        tenants = await sync_to_async(
            lambda: list(
                Business.objects
                .exclude(schema_name="public")
                .values_list("name", flat=True)
            )
        )()

        return tenants


@strawberry.type
class SuperAdminLoginPayload:
    token:    str
    admin_id: int
    name:     str
    email:    str


def _extract_bearer_token(info) -> str | None:
    """Extract Bearer token from Authorization header."""
    ctx     = info.context
    request = getattr(ctx, "request", None)
    if not request:
        return None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


super_admin_schema = strawberry.Schema(
    query=SuperAdminQuery,
    mutation=SuperAdminMutation,
)


# ======================================================
# HEALTH CHECK
# ======================================================

def platform_status(request):
    return JsonResponse({
        "status":  "ok",
        "message": "Hoppers Business Platform — public schema",
    })


# ======================================================
# URL PATTERNS
# ======================================================

urlpatterns = [
    # Platform-level Django admin.
    # Operates in the public schema — use this to create and
    # manage Business, Domain, and SuperAdmin records.
    path("admin/", admin.site.urls),

    # Simple HTTP health check (no GraphQL overhead).
    path("status/", platform_status),

    # Public GraphQL endpoint.
    # Mobile app calls this for all pre-auth mutations:
    #   googleAuth, requestRegistration, verifyRegistration, login
    # graphiql=True keeps the browser IDE in DEBUG mode.
    path(
        "auth/",
        csrf_exempt(
            PublicGraphQLView.as_view(schema=public_schema, graphiql=True)
        ),
    ),

    # SuperAdmin-only GraphQL endpoint.
    # Not accessible to regular employees or admins.
    # Authentication via superAdminLogin mutation.
    path(
        "super/graphql/",
        csrf_exempt(
            AsyncGraphQLView.as_view(schema=super_admin_schema, graphiql=True)
        ),
    ),
]