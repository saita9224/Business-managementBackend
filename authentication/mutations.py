# authentication/mutations.py

import strawberry
from graphql import GraphQLError
from asgiref.sync import sync_to_async

from .services import find_employee_by_email, build_auth_payload


@strawberry.type
class LoginPayload:
    token:       str
    user_id:     int
    name:        str
    email:       str
    roles:       list[str]
    permissions: list[str]
    schema_name: str   # subdomain the app must use for all future requests


@strawberry.type
class AuthMutation:

    @strawberry.mutation
    async def login(self, email: str, password: str) -> LoginPayload:
        """
        Authenticate an employee with email + password.

        Multi-tenant aware — scans all tenant schemas to find the
        employee, so the mobile app does not need to know the subdomain
        before logging in. schema_name is returned so the app can
        route all future requests to the correct tenant endpoint.
        """

        employee, schema_name = await sync_to_async(find_employee_by_email)(email)

        if not employee:
            raise GraphQLError("Invalid email or password")

        if not employee.check_password(password):
            raise GraphQLError("Invalid email or password")

        data = build_auth_payload(employee, schema_name)

        return LoginPayload(
            token=       data["token"],
            user_id=     data["user_id"],
            name=        data["name"],
            email=       data["email"],
            roles=       data["roles"],
            permissions= data["permissions"],
            schema_name= data["schema_name"],
        )