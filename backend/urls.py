# backend/urls.py
from django.contrib import admin
from django.conf import settings
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
 
from strawberry.django.views import AsyncGraphQLView
from .schema import schema
 
from expenses.dataloaders   import create_expenses_dataloaders
from inventory.dataloaders  import create_inventory_dataloaders
from POS.dataloaders        import create_pos_dataloaders
from hr.dataloaders         import create_hr_dataloaders
 
from backend.public_urls import public_schema
 
 
class CustomGraphQLView(AsyncGraphQLView):
    """
    Extends AsyncGraphQLView to inject per-request dataloaders
    into the GraphQL context.
 
    No tenant-scoping code is needed here — by the time a
    request reaches this view, TenantMainMiddleware has already
    set the PostgreSQL search_path to the correct tenant schema.
    All ORM queries transparently hit the right tables.
    """
 
    async def get_context(self, request, response):
        base_context = await super().get_context(request, response)
 
        # ── Expenses ──────────────────────────────────────────
        expenses_loaders = create_expenses_dataloaders()
        base_context.supplier_loader             = expenses_loaders["supplier_loader"]
        base_context.product_loader              = expenses_loaders["product_loader"]
        base_context.payments_by_expense_loader  = expenses_loaders["payments_by_expense_loader"]
        base_context.expenses_by_supplier_loader = expenses_loaders["expenses_by_supplier_loader"]
        base_context.payment_total_loader        = expenses_loaders["payment_total_loader"]
 
        # ── Inventory ─────────────────────────────────────────
        for key, loader in create_inventory_dataloaders().items():
            setattr(base_context, key, loader)
 
        # ── POS ───────────────────────────────────────────────
        for key, loader in create_pos_dataloaders().items():
            setattr(base_context, key, loader)
 
        # ── HR ────────────────────────────────────────────────
        for key, loader in create_hr_dataloaders().items():
            setattr(base_context, key, loader)
 
        # ── Expose the current tenant on context ───────────────
        # request.tenant is set by TenantMainMiddleware.
        # Resolvers can access info.context.tenant if they ever
        # need to know which business they're operating in
        # (e.g. for logging, cross-tenant super-admin features).
        base_context.tenant = getattr(request, 'tenant', None)
 
        return base_context
 
 
urlpatterns = [
    # Django admin — scoped to the current tenant's schema.
    # Each tenant's admin shows only that tenant's data.
    path("admin/", admin.site.urls),
 
    # GraphQL endpoint — identical path as before.
    # graphiql=True keeps the browser IDE available in DEBUG mode.
    path(
        "graphql/",
        csrf_exempt(
            CustomGraphQLView.as_view(
                schema=schema,
                graphiql=settings.GRAPHQL_IDE_ENABLED,
            )
        )
    ),
 
    # Public auth — googleAuth, requestRegistration, verifyRegistration, login
    # Mounted here (in addition to public_urls.py) so it resolves even when
    # django-tenants routes the request to this tenant urlconf based on
    # hostname → Domain lookup. Uses the same public_schema, so behavior is
    # identical no matter which urlconf served the request.
    path(
        "auth/",
        csrf_exempt(
            AsyncGraphQLView.as_view(
                schema=public_schema,
                graphiql=settings.GRAPHQL_IDE_ENABLED,
            )
        ),
    ),
]
