# authentication/mutations.py

import strawberry
import typing

from graphql import GraphQLError
from asgiref.sync import sync_to_async
from strawberry.types import Info

from .services import (
    find_employee_by_email,
    find_all_employees_by_email,
    find_employee_by_email_in_schema,
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
class BusinessChoice:
    schema_name:   str
    business_name: str


@strawberry.type
class LoginChoicePayload:
    """
    Returned instead of LoginPayload when the email + password pair
    is valid in more than one business. The client must call
    loginWithBusiness with the chosen schemaName to complete login.
    """
    message: str
    choices: list[BusinessChoice]


# GraphQL union: login() can return either a completed session or a
# list of businesses to choose from.
LoginResult = strawberry.union("LoginResult", (LoginPayload, LoginChoicePayload))


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
    ) -> LoginResult:
        """
        Checks the password-email pair against every business where
        this email exists. If it's valid in exactly one, logs in
        directly (unchanged behavior for the common case). If it's
        valid in more than one, returns a LoginChoicePayload instead
        of issuing a token — the client must then call
        loginWithBusiness with the chosen schemaName.
        """
        email_clean = email.strip().lower()

        matches = await sync_to_async(find_all_employees_by_email)(email_clean)

        if not matches:
            raise GraphQLError("Invalid email or password")

        # Check the password against every match — password is what
        # discriminates which business the user means, before we ever
        # ask them to choose. Most logins only match one business, so
        # this resolves immediately without any ambiguity prompt.
        valid_matches = [
            m for m in matches
            if m["employee"].check_password(password)
        ]

        if not valid_matches:
            raise GraphQLError("Invalid email or password")

        if len(valid_matches) == 1:
            match = valid_matches[0]
            data = await sync_to_async(build_auth_payload)(
                match["employee"], match["schema_name"]
            )
            return LoginPayload(
                token=             data["token"],
                user_id=           data["user_id"],
                name=              data["name"],
                email=             data["email"],
                roles=             data["roles"],
                permissions=       data["permissions"],
                schema_name=       data["schema_name"],
                is_email_verified= match["employee"].is_email_verified,
            )

        # Same email + same password valid in 2+ businesses — ask the
        # user to choose. No token is issued here since we don't yet
        # know which tenant's permissions should be in it.
        return LoginChoicePayload(
            message="This email is used in more than one business. Please choose which one to log in to.",
            choices=[
                BusinessChoice(
                    schema_name=m["schema_name"],
                    business_name=m["business_name"],
                )
                for m in valid_matches
            ],
        )

    @strawberry.mutation
    async def login_with_business(
        self,
        email:       str,
        password:    str,
        schema_name: str,
    ) -> LoginPayload:
        """
        Second step of the disambiguation flow: the client already
        knows (from a prior LoginChoicePayload) that this email +
        password is valid in this specific schema. Re-validates and
        issues a token scoped to that business.
        """
        employee = await sync_to_async(find_employee_by_email_in_schema)(
            email.strip().lower(), schema_name.strip()
        )

        if not employee:
            raise GraphQLError("Invalid email or password")

        if not employee.check_password(password):
            raise GraphQLError("Invalid email or password")

        data = await sync_to_async(build_auth_payload)(
            employee, schema_name.strip()
        )

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

        data = await sync_to_async(build_auth_payload)(
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

        data = await sync_to_async(build_auth_payload)(
            employee, schema_name
        )

        return ResetPasswordPayload(
            token=       data["token"],
            user_id=     data["user_id"],
            name=        data["name"],
            email=       data["email"],
            roles=       data["roles"],
            permissions= data["permissions"],
            schema_name= data["schema_name"],
        )