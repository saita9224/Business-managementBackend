# employees/mutations.py

import typing
import strawberry
from strawberry.types import Info
from asgiref.sync import sync_to_async

from .decorators import permission_required
from .types import (
    EmployeeType,
    RoleType,
    PermissionType,
    RolePermissionType,
    EmployeeInput,
)
from . import services


# ======================================================
# INPUT TYPES
# ======================================================

@strawberry.input
class OnboardEmployeeInput:
    name:             str
    email:            str
    password:         str
    permission_codes: typing.List[str]
    phone:            typing.Optional[str] = None


# ======================================================
# PAYLOAD TYPES
# ======================================================

@strawberry.type
class VerifyEmailPayload:
    success: bool
    message: str


# ======================================================
# MUTATIONS
# ======================================================

@strawberry.type
class EmployeeMutation:

    # ── ROLE ───────────────────────────────────────────

    @strawberry.mutation
    @permission_required("role.create")
    def create_role(
        self,
        info:        Info,
        name:        str,
        description: typing.Optional[str] = None,
    ) -> RoleType:
        role = services.create_role(name, description)
        return RoleType(
            id=role.id,
            name=role.name,
            description=role.description,
        )

    @strawberry.mutation
    @permission_required("role.update")
    def update_role(
        self,
        info:        Info,
        id:          int,
        name:        typing.Optional[str] = None,
        description: typing.Optional[str] = None,
    ) -> RoleType:
        role = services.update_role(id, name=name, description=description)
        return RoleType(
            id=role.id,
            name=role.name,
            description=role.description,
        )

    @strawberry.mutation
    @permission_required("role.delete")
    def delete_role(self, info: Info, id: int) -> bool:
        return services.delete_role(id)

    # ── PERMISSION ─────────────────────────────────────

    @strawberry.mutation
    @permission_required("role.create")
    def create_permission(
        self,
        info:        Info,
        code:        str,
        description: typing.Optional[str] = None,
    ) -> PermissionType:
        perm = services.create_permission(code, description)
        return PermissionType(
            id=perm.id,
            name=perm.name,
            description=perm.description,
        )

    @strawberry.mutation
    @permission_required("role.update")
    def update_permission(
        self,
        info:        Info,
        id:          int,
        name:        typing.Optional[str] = None,
        description: typing.Optional[str] = None,
    ) -> PermissionType:
        perm = services.update_permission(id, name=name, description=description)
        return PermissionType(
            id=perm.id,
            name=perm.name,
            description=perm.description,
        )

    @strawberry.mutation
    @permission_required("role.delete")
    def delete_permission(self, info: Info, id: int) -> bool:
        return services.delete_permission(id)

    # ── ROLE ↔ PERMISSION ──────────────────────────────

    @strawberry.mutation
    @permission_required("role.update")
    def assign_permission_to_role(
        self,
        info:          Info,
        role_id:       int,
        permission_id: int,
    ) -> RolePermissionType:
        link = services.assign_permission_to_role(role_id, permission_id)
        return RolePermissionType(
            id=link.id,
            role=RoleType(
                id=link.role.id,
                name=link.role.name,
                description=link.role.description,
            ),
            permission=PermissionType(
                id=link.permission.id,
                name=link.permission.name,
                description=link.permission.description,
            ),
        )

    @strawberry.mutation
    @permission_required("role.update")
    def remove_permission_from_role(
        self,
        info:          Info,
        role_id:       int,
        permission_id: int,
    ) -> bool:
        return services.remove_permission_from_role(role_id, permission_id)

    # ── CREATE EMPLOYEE ────────────────────────────────

    @strawberry.mutation
    @permission_required("employee.create")
    async def create_employee(
        self,
        info: Info,
        data: EmployeeInput,
    ) -> EmployeeType:
        """
        Create an employee with named roles and send a welcome
        email containing their verification PIN.
        """
        from django.db import connection
        from tenants.models import Business
        from authentication.email_service import send_employee_verification_pin

        employee, plain_password = await sync_to_async(services.create_employee)(
            name=      data.name,
            email=     data.email,
            phone=     data.phone,
            password=  data.password,
            role_names=data.role_names,
        )

        # Generate verification PIN
        pin = await sync_to_async(
            services.create_employee_verification_pin
        )(employee)

        # Get business name for the email template
        try:
            business = await sync_to_async(Business.objects.get)(
                schema_name=connection.schema_name
            )
            business_name = business.name
        except Exception:
            business_name = "Your Company"

        # Send welcome email with PIN and temporary password
        await sync_to_async(send_employee_verification_pin)(
            email=             employee.email,
            employee_name=     employee.name,
            business_name=     business_name,
            pin=               pin,
            temporary_password=plain_password,
        )

        return employee

    # ── UPDATE EMPLOYEE ────────────────────────────────

    @strawberry.mutation
    @permission_required("employee.update")
    def update_employee(
        self,
        info:       Info,
        id:         int,
        name:       typing.Optional[str]            = None,
        email:      typing.Optional[str]            = None,
        phone:      typing.Optional[str]            = None,
        password:   typing.Optional[str]            = None,
        role_names: typing.Optional[typing.List[str]] = None,
    ) -> EmployeeType:
        return services.update_employee(
            employee_id=id,
            name=       name,
            email=      email,
            phone=      phone,
            password=   password,
            role_names= role_names,
        )

    # ── DELETE EMPLOYEE ────────────────────────────────

    @strawberry.mutation
    @permission_required("employee.delete")
    def delete_employee(self, info: Info, id: int) -> bool:
        return services.delete_employee(id)

    # ── ONBOARD EMPLOYEE — ATOMIC ──────────────────────

    @strawberry.mutation
    @permission_required("employee.create")
    async def onboard_employee(
        self,
        info: Info,
        data: OnboardEmployeeInput,
    ) -> EmployeeType:
        """
        Create an employee with granular permissions in a single
        atomic transaction, then send a welcome email with their
        verification PIN and temporary password.
        """
        from django.db import connection
        from tenants.models import Business
        from authentication.email_service import send_employee_verification_pin

        employee, plain_password = await sync_to_async(services.onboard_employee)(
            name=            data.name,
            email=           data.email,
            phone=           data.phone,
            password=        data.password,
            permission_codes=data.permission_codes,
        )

        # Generate verification PIN
        pin = await sync_to_async(
            services.create_employee_verification_pin
        )(employee)

        # Get business name for the email template
        try:
            business = await sync_to_async(Business.objects.get)(
                schema_name=connection.schema_name
            )
            business_name = business.name
        except Exception:
            business_name = "Your Company"

        # Send welcome email
        await sync_to_async(send_employee_verification_pin)(
            email=             employee.email,
            employee_name=     employee.name,
            business_name=     business_name,
            pin=               pin,
            temporary_password=plain_password,
        )

        return employee

    # ── VERIFY EMAIL ───────────────────────────────────

    @strawberry.mutation
    async def verify_email(self, info: Info, pin: str) -> VerifyEmailPayload:
        """
        Called by an authenticated employee to verify their email.
        Requires a valid JWT in the Authorization header.
        The PIN was sent in their welcome email when their account
        was created — it has no expiry.
        """
        ctx  = info.context
        user = (
            ctx.get("user") if isinstance(ctx, dict)
            else getattr(ctx, "user", None)
        )

        if not user:
            raise Exception("Authentication required")

        if user.is_email_verified:
            return VerifyEmailPayload(
                success=False,
                message="Your email is already verified.",
            )

        try:
            await sync_to_async(services.verify_employee_email_pin)(
                user, pin.strip()
            )
        except ValueError as exc:
            return VerifyEmailPayload(success=False, message=str(exc))

        return VerifyEmailPayload(
            success=True,
            message="Email verified successfully.",
        )

    # ── RESEND VERIFICATION EMAIL ──────────────────────

    @strawberry.mutation
    async def resend_verification_email(self, info: Info) -> VerifyEmailPayload:
        """
        Resend the verification PIN to the authenticated employee.
        Generates a new PIN (invalidating the old one) and emails it.
        """
        from django.db import connection
        from tenants.models import Business
        from authentication.email_service import send_employee_verification_pin

        ctx  = info.context
        user = (
            ctx.get("user") if isinstance(ctx, dict)
            else getattr(ctx, "user", None)
        )

        if not user:
            raise Exception("Authentication required")

        if user.is_email_verified:
            return VerifyEmailPayload(
                success=False,
                message="Your email is already verified.",
            )

        pin = await sync_to_async(
            services.create_employee_verification_pin
        )(user)

        try:
            business = await sync_to_async(Business.objects.get)(
                schema_name=connection.schema_name
            )
            business_name = business.name
        except Exception:
            business_name = "Your Company"

        await sync_to_async(send_employee_verification_pin)(
            email=         user.email,
            employee_name= user.name,
            business_name= business_name,
            pin=           pin,
        )

        return VerifyEmailPayload(
            success=True,
            message="Verification PIN resent. Check your email.",
        )