# backend/schema.py

import strawberry

from authentication.schema import AuthQuery, AuthMutation
from employees.schema      import EmployeeQuery, EmployeeMutation
from expenses.schema       import ExpenseQuery, ExpenseMutation
from expenses.dataloaders  import create_expenses_dataloaders
from inventory.schema      import InventoryQuery, InventoryMutation
from inventory.dataloaders import create_inventory_dataloaders
from POS.schema            import POSQuery, POSMutation
from POS.dataloaders       import create_pos_dataloaders
from hr.schema             import HRQuery, HRMutation
from hr.dataloaders        import create_hr_dataloaders
from reports.schema        import ReportQuery

from .middleware import JWTMiddleware


@strawberry.type
class Query(
    AuthQuery,
    EmployeeQuery,
    ExpenseQuery,
    InventoryQuery,
    POSQuery,
    HRQuery,
    ReportQuery,
):
    """Root GraphQL Query — composed from app-level mixins."""
    pass


@strawberry.type
class Mutation(
    AuthMutation,
    EmployeeMutation,
    ExpenseMutation,
    InventoryMutation,
    POSMutation,
    HRMutation,
):
    """Root GraphQL Mutation — composed from app-level mixins."""
    pass


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[JWTMiddleware],
)