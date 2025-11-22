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
    role: str
    


@strawberry.type
class AuthMutation:

    @strawberry.mutation
    def login(self, email: str, password: str) -> LoginPayload:
        
        # Validate employee
        try:
            employee = Employee.objects.get(email=email)
        except Employee.DoesNotExist:
            raise GraphQLError("Invalid email or password")

        # Validate password
        if not employee.check_password(password):
            raise GraphQLError("Invalid email or password")

        # Create JWT
        token = create_jwt_token(employee)

        return LoginPayload(
            token=token,
            user_id=employee.id,
            name=employee.name,
            role=employee.role.name if employee.role else "No Role",
        )
