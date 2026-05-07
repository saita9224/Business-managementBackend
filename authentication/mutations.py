# authentication/mutations.py

import strawberry
from graphql import GraphQLError
from asgiref.sync import sync_to_async
from django_tenants.utils import schema_context

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
    is_email_verified: bool  # app shows verification screen if False


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

    # ── Employee login — email + password ──────────────

    @strawberry.mutation
    async def login(self, email: str, password: str) -> LoginPayload:
        """
        Authenticate an employee with email + password.

        Multi-tenant aware — scans all tenant schemas to find the
        employee so the app does not need to know the subdomain
        before logging in.

        Returns is_email_verified so the app knows whether to show
        the PIN verification screen after login.
        """
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

    # ── Step 1: Request PIN — new Business registration ─

    @strawberry.mutation
    async def request_registration(
        self,
        email:         str,
        business_name: str,
    ) -> RequestRegistrationPayload:
        """
        Step 1 of admin registration via email + password.

        Sends a 6-digit PIN to the provided email.
        The Business/schema is NOT created yet — that happens
        only after the PIN is verified in step 2.

        If a pending registration already exists for this email
        it is replaced, invalidating the old PIN.
        """
        # Prevent registering with an email that already has an account
        existing, _ = await sync_to_async(find_employee_by_email)(
            email.strip().lower()
        )
        if existing:
            raise GraphQLError(
                "An account with this email already exists. "
                "Please log in instead."
            )

        pin = await sync_to_async(create_pending_registration)(
            email.strip().lower(),
            business_name.strip(),
        )

        await sync_to_async(send_registration_pin)(
            email=         email,
            business_name= business_name,
            pin=           pin,
        )

        return RequestRegistrationPayload(
            message="Verification PIN sent. Check your email.",
            email=email,
        )

    # ── Step 2: Verify PIN — create Business + Admin ────

    @strawberry.mutation
    async def verify_registration(
        self,
        email:    str,
        pin:      str,
        name:     str,      # admin's display name (not collected at step 1)
        password: str,      # admin sets their own password here
    ) -> VerifyRegistrationPayload:
        """
        Step 2 of admin registration.

        Verifies the PIN sent in step 1, creates the Business schema
        and Admin Employee, sets the admin's name and password, and
        returns a JWT — the admin is logged in immediately.
        """
        try:
            pending = await sync_to_async(verify_pending_registration)(
                email.strip().lower(),
                pin.strip(),
            )
        except ValueError as exc:
            raise GraphQLError(str(exc))

        # Create the tenant and a placeholder admin employee
        employee, schema_name = await sync_to_async(
            complete_pending_registration
        )(pending)

        # Set the name and password supplied at step 2.
        # Must happen inside the correct schema context.
        def _finalise(emp, n, p):
            emp.name = n
            emp.set_password(p)
            emp.save(update_fields=["name", "password"])

        with schema_context(schema_name):
            await sync_to_async(_finalise)(employee, name.strip(), password)

            # Reload with roles + permissions
            employee = await sync_to_async(
                lambda: type(employee).objects
                .prefetch_related("roles__permissions")
                .get(pk=employee.pk)
            )()

        data = build_auth_payload(employee, schema_name, is_new_user=True)

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