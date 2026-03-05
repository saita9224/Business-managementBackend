# authentication/mutations.py

import strawberry
from graphql import GraphQLError
from asgiref.sync import sync_to_async

from employees.models import Employee
from .services import create_jwt_token


@strawberry.type
class LoginPayload:
    token: str
    user_id: int
    name: str
    roles: list[str]
    permissions: list[str]


@strawberry.type
class AuthMutation:

    @strawberry.mutation
    async def login(self, email: str, password: str) -> LoginPayload:

        try:
           employee = await sync_to_async(
              lambda: Employee.objects
              .prefetch_related("roles__permissions")
              .get(email__iexact=email)
              )()
        except Employee.DoesNotExist:
           raise GraphQLError("Invalid email or password")

        if not employee.is_active:
           raise GraphQLError("Account disabled")

        if not employee.check_password(password):
           raise GraphQLError("Invalid email or password")

        token = create_jwt_token(employee)

        roles = [role.name for role in employee.roles.all()]

        permission_set = {
           perm.code
           for role in employee.roles.all()
           for perm in role.permissions.all()
           }

        return LoginPayload(
            token=token,
            user_id=employee.id,
            name=employee.name,
            roles=roles,
            permissions=list(permission_set),
            )