# backend/graphql_context.py

"""
Shared GraphQL context builder.

Both CustomGraphQLView (backend/urls.py) and TenantGraphQLView
(backend/public_urls.py) need identical per-request dataloader
injection. This module is the single source of truth.
"""

from expenses.dataloaders  import create_expenses_dataloaders
from inventory.dataloaders import create_inventory_dataloaders
from POS.dataloaders       import create_pos_dataloaders
from hr.dataloaders        import create_hr_dataloaders


async def inject_dataloaders(base_context, request):
    """Attach per-request dataloaders and tenant to the context."""

    # ── Expenses ──────────────────────────────────────────
    expenses_loaders = create_expenses_dataloaders()
    base_context.supplier_loader             = expenses_loaders["supplier_loader"]
    base_context.product_loader              = expenses_loaders["product_loader"]
    base_context.payments_by_expense_loader  = expenses_loaders["payments_by_expense_loader"]
    base_context.expenses_by_supplier_loader = expenses_loaders["expenses_by_supplier_loader"]
    base_context.payment_total_loader        = expenses_loaders["payment_total_loader"]
    base_context.expense_loader              = expenses_loaders["expense_loader"]

    # ── Inventory ─────────────────────────────────────────
    for key, loader in create_inventory_dataloaders().items():
        setattr(base_context, key, loader)

    # ── POS ───────────────────────────────────────────────
    for key, loader in create_pos_dataloaders().items():
        setattr(base_context, key, loader)

    # ── HR ────────────────────────────────────────────────
    for key, loader in create_hr_dataloaders().items():
        setattr(base_context, key, loader)

    # ── Current tenant ────────────────────────────────────
    base_context.tenant = getattr(request, 'tenant', None)

    return base_context
