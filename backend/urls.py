# backend/urls.py
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt

from strawberry.django.views import AsyncGraphQLView
from .schema import schema

from backend.graphql_context import inject_dataloaders

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
        return await inject_dataloaders(base_context, request)


urlpatterns = [
    # Django admin — scoped to the current tenant's schema.
    path("admin/", admin.site.urls),

    # Tenants REST API (e.g. logo upload)
    path("api/tenants/", include("tenants.urls")),
    path("tenants/", include("tenants.urls")),

    # GraphQL endpoint
    path(
        "graphql/",
        csrf_exempt(
            CustomGraphQLView.as_view(
                schema=schema,
                graphiql=settings.GRAPHQL_IDE_ENABLED,
            )
        )
    ),

    # Public auth
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

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


