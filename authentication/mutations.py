# authentication/mutations.py

import strawberry

from graphql import GraphQLError
from asgiref.sync import sync_to_async

from .services import (
    find_employee_by_email,
    build_auth_payload,
    create_pending_registration,
    verify_pending_registration,
    complete_pending_registration,
)

from .email_service import send_registration_pin


# ======================================================
# PAYLOAD TYPES
# ======================================================

@strawberry.type
class LoginPayload:
    token:             str
    user_id:           int
    name:              str
    email:             str
    roles:             list[str]
    permissions:       list[str]
    schema_name:       str
    is_email_verified: bool


@strawberry.type
class RequestRegistrationPayload:
    message: str
    email:   str


@strawberry.type
class VerifyRegistrationPayload:
    token:       str
    user_id:     int
    name:        str
    email:       str
    roles:       list[str]
    permissions: list[str]
    schema_name: str
    is_new_user: bool


# ======================================================
# MUTATIONS
# ======================================================

@strawberry.type
class AuthMutation:

    # ==================================================
    # LOGIN
    # ==================================================

    @strawberry.mutation
    async def login(
        self,
        email: str,
        password: str,
    ) -> LoginPayload:

        employee, schema_name = await sync_to_async(
            find_employee_by_email
        )(email)

        if not employee:
            raise GraphQLError("Invalid email or password")

        if not employee.check_password(password):
            raise GraphQLError("Invalid email or password")

        data = build_auth_payload(employee, schema_name)

        return LoginPayload(
            token=             data["token"],
            user_id=           data["user_id"],
            name=              data["name"],
            email=             data["email"],
            roles=             data["roles"],
            permissions=       data["permissions"],
            schema_name=       data["schema_name"],
            is_email_verified= employee.is_email_verified,
        )

    # ==================================================
    # REQUEST REGISTRATION
    # ==================================================

    @strawberry.mutation
    async def request_registration(
        self,
        email: str,
        business_name: str,
    ) -> RequestRegistrationPayload:

        existing, _ = await sync_to_async(
            find_employee_by_email
        )(email.strip().lower())

        if existing:
            raise GraphQLError(
                "An account with this email already exists. "
                "Please log in instead."
            )

        pin = await sync_to_async(
            create_pending_registration
        )(
            email.strip().lower(),
            business_name.strip(),
        )

        await sync_to_async(send_registration_pin)(
            email=email,
            business_name=business_name,
            pin=pin,
        )

        return RequestRegistrationPayload(
            message="Verification PIN sent. Check your email.",
            email=email,
        )

    # ==================================================
    # VERIFY REGISTRATION
    # ==================================================

    @strawberry.mutation
    async def verify_registration(
        self,
        email: str,
        pin: str,
        name: str,
        password: str,
    ) -> VerifyRegistrationPayload:

        try:
            pending = await sync_to_async(
                verify_pending_registration
            )(
                email.strip().lower(),
                pin.strip(),
            )

        except ValueError as exc:
            raise GraphQLError(str(exc))

        employee, schema_name = await sync_to_async(
            complete_pending_registration
        )(
            pending,
            name.strip(),
            password,
        )

        data = build_auth_payload(
            employee,
            schema_name,
            is_new_user=True,
        )

        return VerifyRegistrationPayload(
            token=       data["token"],
            user_id=     data["user_id"],
            name=        data["name"],
            email=       data["email"],
            roles=       data["roles"],
            permissions= data["permissions"],
            schema_name= data["schema_name"],
            is_new_user= True,
        )