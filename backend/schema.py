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

# HR
from hr.schema import HRQuery, HRMutation
from hr.dataloaders import create_hr_dataloaders

# -------------------------------------------------
# Middleware
# -------------------------------------------------
from .middleware import JWTMiddleware


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
    HRQuery,
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
    HRMutation,
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