import strawberry

# Import app-level GraphQL schema components
from authentication.schema import AuthQuery, AuthMutation
from employees.schema import EmployeeQuery, EmployeeMutation
from expenses.schema import ExpenseQuery, ExpenseMutation   # 👈 NEW

# JWT Middleware (as extension)
from .middleware import JWTMiddleware


# -------------------------------
# Root Query (combine all queries)
# -------------------------------
@strawberry.type
class Query(
    AuthQuery,
    EmployeeQuery,
    ExpenseQuery,        # 👈 NEW
):
    pass


# -------------------------------
# Root Mutation (combine all mutations)
# -------------------------------
@strawberry.type
class Mutation(
    AuthMutation,
    EmployeeMutation,
    ExpenseMutation,     # 👈 NEW
):
    pass


# -------------------------------
# Build GraphQL Schema
# -------------------------------
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[JWTMiddleware]
)
