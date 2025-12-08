import strawberry

# Import app-level GraphQL schema components
from authentication.schema import AuthQuery, AuthMutation
from employees.schema import EmployeeQuery, EmployeeMutation
from expenses.schema import ExpenseQuery, ExpenseMutation   # ✔ Included properly

# JWT middleware (extension)
from .middleware import JWTMiddleware

# Dataloaders (for context)
from expenses.dataloaders import create_dataloaders


# -------------------------------------------------
# Context Function (replaces the missing backend.context)
# -------------------------------------------------
def get_context(request):
    """
    This function attaches request + dataloaders to GraphQL context.
    It prevents N+1 queries by enabling batched database fetching.
    """
    return {
        "request": request,
        **create_dataloaders(),
    }


# -------------------------------------------------
# Root Query (combine all queries)
# -------------------------------------------------
@strawberry.type
class Query(
    AuthQuery,
    EmployeeQuery,
    ExpenseQuery,       # ✔ Expenses added
):
    pass


# -------------------------------------------------
# Root Mutation (combine all mutations)
# -------------------------------------------------
@strawberry.type
class Mutation(
    AuthMutation,
    EmployeeMutation,
    ExpenseMutation,   # ✔ Expenses added
):
    pass


# -------------------------------------------------
# Build GraphQL Schema
# -------------------------------------------------
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[JWTMiddleware],
)
