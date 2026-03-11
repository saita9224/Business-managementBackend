# backend/urls.py

from django.contrib import admin
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from strawberry.django.views import AsyncGraphQLView
from .schema import schema
from expenses.dataloaders import create_expenses_dataloaders
from inventory.dataloaders import create_inventory_dataloaders
from POS.dataloaders import create_pos_dataloaders


class CustomGraphQLView(AsyncGraphQLView):
    async def get_context(self, request, response):
        base_context = await super().get_context(request, response)

        # ── BUG FIX: was calling create_expenses_dataloaders() 5 times,
        # creating 5 separate loader instances. Call once, inject all.
        expenses_loaders = create_expenses_dataloaders()
        base_context.supplier_loader = expenses_loaders["supplier_loader"]
        base_context.product_loader = expenses_loaders["product_loader"]
        base_context.payments_by_expense_loader = expenses_loaders["payments_by_expense_loader"]
        base_context.expenses_by_supplier_loader = expenses_loaders["expenses_by_supplier_loader"]
        base_context.payment_total_loader = expenses_loaders["payment_total_loader"]

        for key, loader in create_inventory_dataloaders().items():
            setattr(base_context, key, loader)

        for key, loader in create_pos_dataloaders().items():
            setattr(base_context, key, loader)

        return base_context


urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "graphql/",
        csrf_exempt(
            CustomGraphQLView.as_view(schema=schema, graphiql=True)
        )
    ),
]