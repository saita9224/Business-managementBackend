import strawberry

# Import app-level schemas
from authentication.schema import Query as AuthQuery, Mutation as AuthMutation
from employees.schema import Query as EmployeeQuery, Mutation as EmployeeMutation

# JWT Middleware
from .middleware import JWTMiddleware


# Combine Queries (Multi-inheritance)
@strawberry.type
class Query(AuthQuery, EmployeeQuery):
    pass


# Combine Mutations
@strawberry.type
class Mutation(AuthMutation, EmployeeMutation):
    pass


# Create the GraphQL schema
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[JWTMiddleware]   # ⭐ Activate JWT middleware
)
