import strawberry

# Import app-level GraphQL schema components
from authentication.schema import AuthQuery, AuthMutation
from employees.schema import EmployeeQuery, EmployeeMutation

# JWT Middleware (now used as an extension)
from .middleware import JWTMiddleware


# -------------------------------
# Root Query (combine all queries)
# -------------------------------
@strawberry.type
class Query(AuthQuery, EmployeeQuery):
    pass


# -------------------------------
# Root Mutation (combine all mutations)
# -------------------------------
@strawberry.type
class Mutation(AuthMutation, EmployeeMutation):
    pass


# -------------------------------
# Build GraphQL Schema
# -------------------------------
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[JWTMiddleware]   # ✔️ Correct placement
)
