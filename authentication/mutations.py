# authentication/mutations.py

import strawberry
from graphql import GraphQLError

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
    def login(self, email: str, password: str) -> LoginPayload:

        try:
            employee = Employee.objects.get(email=email)
        except Employee.DoesNotExist:
            raise GraphQLError("Invalid email or password")

        if not employee.check_password(password):
            raise GraphQLError("Invalid email or password")

        # Create JWT
        token = create_jwt_token(employee)

        # Multi-role support
        roles = [role.name for role in employee.roles.all()]

        # Union of all permissions
        permission_set = set()
        for role in employee.roles.all():
            for perm in role.permissions.all():
                permission_set.add(perm.code)

        return LoginPayload(
            token=token,
            user_id=employee.id,
            name=employee.name,
            roles=roles,
            permissions=list(permission_set),
        )
