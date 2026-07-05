# authentication/mutations.py

import strawberry

from graphql import GraphQLError
from asgiref.sync import sync_to_async
from strawberry.types import Info

from .services import (
    find_employee_by_email,
    build_auth_payload,
    create_pending_registration,
    verify_pending_registration,
    complete_pending_registration,
    create_password_reset_request,
    complete_password_reset,
)

from .email_service import (
    send_registration_pin,
    send_password_reset_pin,
)


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


@strawberry.type
class RequestPasswordResetPayload:
    message: str
    email:   str


@strawberry.type
class ResetPasswordPayload:
    token:       str
    user_id:     int
    name:        str
    email:       str
    roles:       list[str]
    permissions: list[str]
    schema_name: str


@strawberry.type
class AuthMutation:

    @strawberry.mutation
    async def login(
        self,
        info: Info,
        email: str,
        password: str,
    ) -> LoginPayload:
        # NOTE: login always arrives through the public schema (/auth/ is
        # mounted on the bare domain, never a tenant subdomain — see
        # lib/graphql.js PUBLIC_URL). request.tenant is therefore always
        # the public tenant here, so we can't resolve which business the
        # user belongs to from tenant middleware. Instead we search across
        # all tenant schemas by email, same as googleAuth and the password
        # reset flow already do.
        employee, resolved_schema_name = await sync_to_async(
            find_employee_by_email
        )(email.strip().lower())

        if not employee:
            raise GraphQLError("Invalid email or password")

        if not employee.check_password(password):
            raise GraphQLError("Invalid email or password")

        data = build_auth_payload(employee, resolved_schema_name)

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

    @strawberry.mutation
    async def request_password_reset(
        self,
        email: str,
    ) -> RequestPasswordResetPayload:
        try:
            employee, schema_name, pin = await sync_to_async(
                create_password_reset_request
            )(email.strip().lower())

            await sync_to_async(send_password_reset_pin)(
                email=email.strip().lower(),
                name=employee.name,
                pin=pin,
            )

        except ValueError:
            pass

        return RequestPasswordResetPayload(
            message="If an account exists for this email, a reset PIN has been sent.",
            email=email.strip().lower(),
        )

    @strawberry.mutation
    async def reset_password(
        self,
        email:        str,
        pin:          str,
        new_password: str,
    ) -> ResetPasswordPayload:

        try:
            employee, schema_name = await sync_to_async(
                complete_password_reset
            )(
                email.strip().lower(),
                pin.strip(),
                new_password,
            )
        except ValueError as exc:
            raise GraphQLError(str(exc))

        data = build_auth_payload(employee, schema_name)

        return ResetPasswordPayload(
            token=       data["token"],
            user_id=     data["user_id"],
            name=        data["name"],
            email=       data["email"],
            roles=       data["roles"],
            permissions= data["permissions"],
            schema_name= data["schema_name"],
        )