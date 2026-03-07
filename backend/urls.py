# backend/urls.py
from django.contrib import admin
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from strawberry.django.views import AsyncGraphQLView
from strawberry.django.context import StrawberryDjangoContext
from .schema import schema
from expenses.dataloaders import create_expenses_dataloaders
from inventory.dataloaders import create_inventory_dataloaders
from POS.dataloaders import create_pos_dataloaders


class CustomGraphQLView(AsyncGraphQLView):
    async def get_context(self, request, response):
        # Get the default Strawberry context
        base_context = await super().get_context(request, response)
        # Inject all dataloaders into it
        base_context.supplier_loader = create_expenses_dataloaders()["supplier_loader"]
        base_context.product_loader = create_expenses_dataloaders()["product_loader"]
        base_context.payments_by_expense_loader = create_expenses_dataloaders()["payments_by_expense_loader"]
        base_context.expenses_by_supplier_loader = create_expenses_dataloaders()["expenses_by_supplier_loader"]
        base_context.payment_total_loader = create_expenses_dataloaders()["payment_total_loader"]
        # Inventory & POS loaders
        for key, loader in create_inventory_dataloaders().items():
            setattr(base_context, key, loader)
        for key, loader in create_pos_dataloaders().items():
            setattr(base_context, key, loader)
        return base_context


urlpatterns = [
    path('admin/', admin.site.urls),
    path(
        'graphql/',
        csrf_exempt(
            CustomGraphQLView.as_view(schema=schema, graphiql=True)
        )
    ),
]