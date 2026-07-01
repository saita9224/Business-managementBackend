# backend/public_urls.py

import strawberry
from django.contrib import admin
from django.conf import settings
from django.urls import path
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from strawberry.django.views import AsyncGraphQLView

from authentication.social_mutations import SocialAuthMutation
from authentication.mutations import AuthMutation

from expenses.dataloaders  import create_expenses_dataloaders
from inventory.dataloaders import create_inventory_dataloaders
from POS.dataloaders       import create_pos_dataloaders
from hr.dataloaders        import create_hr_dataloaders
from backend.schema        import schema


# ======================================================
# PUBLIC GRAPHQL SCHEMA
# ======================================================

@strawberry.type
class PublicQuery:
    @strawberry.field
    def status(self) -> str:
        return "ok"


@strawberry.type
class PublicMutation(SocialAuthMutation, AuthMutation):
    pass


public_schema = strawberry.Schema(
    query=PublicQuery,
    mutation=PublicMutation,
)


class PublicGraphQLView(AsyncGraphQLView):
    pass


# ======================================================
# SUPER ADMIN SCHEMA
# ======================================================

@strawberry.type
class SuperAdminQuery:
    @strawberry.field
    def super_status(self) -> str:
        return "SuperAdmin endpoint active"


@strawberry.type
class SuperAdminMutation:

    @strawberry.mutation
    async def super_admin_login(
        self,
        email:    str,
        password: str,
    ) -> "SuperAdminLoginPayload":
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
# TENANT GRAPHQL VIEW
# Used in development when requests arrive via bare IP.
# XTenantMiddleware reads X-Tenant header and switches
# the schema before this view handles the request.
# In production this view is never used — tenant requests
# arrive on subdomains and are routed to backend/urls.py.
# ======================================================

class TenantGraphQLView(AsyncGraphQLView):
    """
    Serves tenant GraphQL requests in development.
    Identical to CustomGraphQLView in backend/urls.py —
    same dataloaders, same schema, same JWTMiddleware.
    """

    async def get_context(self, request, response):
        base_context = await super().get_context(request, response)

        expenses_loaders = create_expenses_dataloaders()
        base_context.supplier_loader             = expenses_loaders["supplier_loader"]
        base_context.product_loader              = expenses_loaders["product_loader"]
        base_context.payments_by_expense_loader  = expenses_loaders["payments_by_expense_loader"]
        base_context.expenses_by_supplier_loader = expenses_loaders["expenses_by_supplier_loader"]
        base_context.payment_total_loader        = expenses_loaders["payment_total_loader"]

        for key, loader in create_inventory_dataloaders().items():
            setattr(base_context, key, loader)

        for key, loader in create_pos_dataloaders().items():
            setattr(base_context, key, loader)

        for key, loader in create_hr_dataloaders().items():
            setattr(base_context, key, loader)

        base_context.tenant = getattr(request, 'tenant', None)

        return base_context


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
    path("admin/", admin.site.urls),
    path("status/", platform_status),

    # Public auth — googleAuth, requestRegistration, verifyRegistration, login
    path(
        "auth/",
        csrf_exempt(
            PublicGraphQLView.as_view(
                schema=public_schema,
                graphiql=settings.GRAPHQL_IDE_ENABLED,
            )
        ),
    ),

    # SuperAdmin only
    path(
        "super/graphql/",
        csrf_exempt(
            AsyncGraphQLView.as_view(
                schema=super_admin_schema,
                graphiql=settings.GRAPHQL_IDE_ENABLED,
            )
        ),
    ),

    # Tenant GraphQL — development only (bare IP access)
    # In production, tenant requests use subdomains → backend/urls.py
    # In development, XTenantMiddleware + this path handles them
    path(
        "graphql/",
        csrf_exempt(
            TenantGraphQLView.as_view(
                schema=schema,
                graphiql=settings.GRAPHQL_IDE_ENABLED,
            )
        ),
    ),
]
