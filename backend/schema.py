# backend/schema.py

import strawberry

# -------------------------------------------------
# App-level GraphQL schema components
# -------------------------------------------------

# Authentication
from authentication.schema import AuthQuery, AuthMutation

# Employees
from employees.schema import EmployeeQuery, EmployeeMutation

# Expenses
from expenses.schema import ExpenseQuery, ExpenseMutation
from expenses.dataloaders import create_expenses_dataloaders


# Inventory
from inventory.schema import InventoryQuery, InventoryMutation
from inventory.dataloaders import create_inventory_dataloaders

# POS
from POS.schema import POSQuery, POSMutation
from POS.dataloaders import create_pos_dataloaders

# -------------------------------------------------
# Middleware
# -------------------------------------------------
from .middleware import JWTMiddleware


# -------------------------------------------------
# Context Function (single source of truth)
# -------------------------------------------------
def get_context(request):
    """
    Attaches request + all dataloaders to GraphQL context.

    This is the ONLY place context is built.
    Prevents N+1 queries via request-scoped dataloaders.
    """

    return {
        "request": request,
        "user": request.user,  # unified access (POS, Inventory, Expenses)
        # ------------------
        # Dataloaders
        # ------------------
        **create_expense_dataloaders(),
        **create_inventory_dataloaders(),
        **create_pos_dataloaders(),
    }


# -------------------------------------------------
# Root Query (composition only)
# -------------------------------------------------
@strawberry.type
class Query(
    AuthQuery,
    EmployeeQuery,
    ExpenseQuery,
    InventoryQuery,
    POSQuery,
):
    """
    Root GraphQL Query.

    Composed from app-level query mixins.
    """
    pass


# -------------------------------------------------
# Root Mutation (composition only)
# -------------------------------------------------
@strawberry.type
class Mutation(
    AuthMutation,
    EmployeeMutation,
    ExpenseMutation,
    InventoryMutation,
    POSMutation,
):
    """
    Root GraphQL Mutation.

    Composed from app-level mutation mixins.
    """
    pass


# -------------------------------------------------
# Build GraphQL Schema
# -------------------------------------------------
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[JWTMiddleware],
)
