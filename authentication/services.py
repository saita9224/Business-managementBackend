# authentication/services.py

"""
JWT creation and decoding, plus all business logic:

  - find_existing_google_user()
  - create_new_tenant_and_admin()
  - find_employee_by_email()
  - build_auth_payload()
  - create_pending_registration()
  - verify_pending_registration()
  - complete_pending_registration()
  - create_super_admin_jwt()
  - decode_super_admin_jwt()

PendingRegistration lives in tenants.models (a pure SHARED_APP)
so its table is guaranteed to exist in the public schema.
generate_pin() stays in authentication.models and is imported from there.
"""

import re
import jwt
import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from asgiref.sync import sync_to_async
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)

JWT_SECRET           = getattr(settings, "JWT_SECRET", settings.SECRET_KEY)
ALGORITHM            = getattr(settings, "JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRES = getattr(settings, "JWT_ACCESS_EXPIRES_SECONDS", 3600)


# ======================================================
# EMPLOYEE JWT
# ======================================================

def create_jwt_token(
    employee,
    schema_name: str,
    expires_in: int = ACCESS_TOKEN_EXPIRES,
) -> str:
    """
    Create a signed JWT for an employee.
    """
    now = timezone.now()

    payload = {
        "user_id":     employee.id,
        "schema_name": schema_name,
        "role":        "employee",
        "iat":         int(now.timestamp()),
        "exp":         int((now + timedelta(seconds=expires_in)).timestamp()),
    }

    token = jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

    if isinstance(token, bytes):
        token = token.decode("utf-8")

    return token


def _load_employee_from_schema(schema_name: str, user_id: int):
    """
    Synchronous helper that performs ALL tenant-scoped ORM work
    inside schema_context.

    Required because schema_context is thread-local and does not
    survive async/sync thread boundaries.
    """
    from employees.models import Employee

    with schema_context(schema_name):
        return Employee.objects.get(id=user_id)


async def decode_jwt_token(token: str):
    """
    Decode an employee JWT and return the matching Employee,
    or None on any failure.
    """
    from jwt import ExpiredSignatureError, InvalidTokenError, DecodeError

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])

        if payload.get("role") == "superadmin":
            logger.debug("Employee decoder rejected superadmin token")
            return None

        user_id     = payload.get("user_id")
        schema_name = payload.get("schema_name")

        if not user_id or not schema_name:
            logger.debug("JWT missing user_id or schema_name")
            return None

        employee = await sync_to_async(
            _load_employee_from_schema
        )(schema_name, user_id)

        if not employee.is_active:
            return None

        return employee

    except (ExpiredSignatureError, InvalidTokenError, DecodeError):
        logger.debug("JWT decode failed — expired or invalid")
        return None

    except Exception:
        logger.debug("JWT decode failed — employee not found or schema error")
        return None


# ======================================================
# SUPER ADMIN JWT
# ======================================================

def create_super_admin_jwt(
    admin,
    expires_in: int = ACCESS_TOKEN_EXPIRES,
) -> str:
    """
    Create a JWT for the SuperAdmin.
    """
    now = timezone.now()

    payload = {
        "super_admin_id": admin.id,
        "role":           "superadmin",
        "iat":            int(now.timestamp()),
        "exp":            int((now + timedelta(seconds=expires_in)).timestamp()),
    }

    token = jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

    if isinstance(token, bytes):
        token = token.decode("utf-8")

    return token


async def decode_super_admin_jwt(token: str):
    """
    Decode a SuperAdmin JWT.
    """
    from jwt import ExpiredSignatureError, InvalidTokenError, DecodeError
    from tenants.models import SuperAdmin

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])

        if payload.get("role") != "superadmin":
            logger.debug("Token rejected — not a superadmin token")
            return None

        admin_id = payload.get("super_admin_id")

        if not admin_id:
            return None

        admin = await sync_to_async(SuperAdmin.objects.get)(
            id=admin_id,
            is_active=True,
        )

        return admin

    except (ExpiredSignatureError, InvalidTokenError, DecodeError):
        logger.debug("SuperAdmin JWT decode failed — expired or invalid")
        return None

    except Exception:
        logger.debug("SuperAdmin JWT decode failed — admin not found")
        return None


# ======================================================
# AUTH PAYLOAD
# ======================================================

def build_auth_payload(
    employee,
    schema_name: str,
    is_new_user: bool = False,
) -> dict:
    """
    Shared auth payload builder.
    """
    token = create_jwt_token(employee, schema_name)

    roles = [role.name for role in employee.roles.all()]

    permissions = list({
        perm.code
        for role in employee.roles.all()
        for perm in role.permissions.all()
    })

    return {
        "token":       token,
        "user_id":     employee.id,
        "name":        employee.name,
        "email":       employee.email,
        "roles":       roles,
        "permissions": permissions,
        "schema_name": schema_name,
        "is_new_user": is_new_user,
    }


# ======================================================
# GOOGLE AUTH
# ======================================================

def find_existing_google_user(google_id: str, email: str):
    """
    Search every tenant schema for a Google user.
    """
    from tenants.models import Business
    from employees.models import Employee, SocialAccount

    for tenant in Business.objects.exclude(schema_name="public"):

        with schema_context(tenant.schema_name):

            # Stage 1 — SocialAccount lookup
            try:
                account = (
                    SocialAccount.objects
                    .select_related("employee")
                    .get(provider="google", provider_id=google_id)
                )

                return account.employee, tenant.schema_name

            except SocialAccount.DoesNotExist:
                pass

            # Stage 2 — email fallback
            if email:
                try:
                    employee = Employee.objects.get(
                        email__iexact=email,
                        is_active=True,
                    )

                    SocialAccount.objects.create(
                        employee=employee,
                        provider="google",
                        provider_id=google_id,
                        email=email,
                        name=employee.name,
                        picture_url=None,
                    )

                    logger.info(
                        "Auto-linked Google account for %s in schema %s",
                        email,
                        tenant.schema_name,
                    )

                    return employee, tenant.schema_name

                except Employee.DoesNotExist:
                    pass

    return None, None


# ======================================================
# TENANT CREATION
# ======================================================

def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "_", slug)
    slug = re.sub(r"^-+|-+$", "", slug)

    if slug and slug[0].isdigit():
        slug = "b_" + slug

    return slug[:50]


def _unique_schema_name(base: str) -> str:
    from tenants.models import Business

    name, counter = base, 1

    while Business.objects.filter(schema_name=name).exists():
        name = f"{base}_{counter}"
        counter += 1

    return name


def create_new_tenant_and_admin(
    user_info: dict,
    business_name: str,
    set_unusable_password: bool = True,
) -> tuple:
    """
    Create a new tenant schema and admin employee.
    """
    from tenants.models import Business, Domain
    from employees.models import Employee, Role, SocialAccount
    from django.db import transaction

    base_slug   = _slugify(business_name)
    schema_name = _unique_schema_name(base_slug)

    business = Business(
        schema_name=schema_name,
        name=business_name,
    )

    business.save()

    Domain.objects.create(
        tenant=business,
        domain=f"{schema_name}.localhost",
        is_primary=True,
    )

    with schema_context(schema_name):

        with transaction.atomic():

            admin_role, _ = Role.objects.get_or_create(name="Admin")

            email = (
                user_info["email"]
                or f"google_{user_info.get('provider_id')}@noemail.local"
            )

            employee = Employee(
                name=user_info.get("name") or "Admin",
                email=email,
                is_active=True,
                is_email_verified=True,
            )

            if set_unusable_password:
                employee.set_unusable_password()

            employee.save()

            employee.roles.add(admin_role)

            if user_info.get("provider_id"):
                SocialAccount.objects.create(
                    employee=employee,
                    provider="google",
                    provider_id=user_info["provider_id"],
                    email=email,
                    name=user_info.get("name") or "",
                    picture_url=user_info.get("picture_url"),
                )

    logger.info(
        "Created new tenant '%s' (schema: %s)",
        business_name,
        schema_name,
    )

    return employee, schema_name


# ======================================================
# EMAIL+PASSWORD LOGIN
# ======================================================

def find_employee_by_email(email: str):
    """
    Search every tenant schema for an Employee with this email.
    """
    from tenants.models import Business
    from employees.models import Employee

    for tenant in Business.objects.exclude(schema_name="public"):

        with schema_context(tenant.schema_name):

            try:
                employee = (
                    Employee.objects
                    .prefetch_related("roles__permissions")
                    .get(email__iexact=email, is_active=True)
                )

                return employee, tenant.schema_name

            except Employee.DoesNotExist:
                continue

    return None, None


# ======================================================
# PENDING REGISTRATION
# ======================================================

def create_pending_registration(email: str, business_name: str) -> str:
    """
    Create or replace a PendingRegistration.
    """
    from tenants.models import PendingRegistration
    from authentication.models import generate_pin

    pin = generate_pin()

    PendingRegistration.objects.filter(
        email__iexact=email
    ).delete()

    PendingRegistration.objects.create(
        email=email,
        business_name=business_name,
        pin=pin,
    )

    logger.info("Created pending registration for %s", email)

    return pin


def verify_pending_registration(email: str, pin: str):
    """
    Verify a pending registration PIN.
    """
    from tenants.models import PendingRegistration

    try:
        pending = PendingRegistration.objects.get(
            email__iexact=email
        )

    except PendingRegistration.DoesNotExist:
        raise ValueError(
            "No pending registration found for this email. "
            "Please request a new PIN."
        )

    if pending.is_expired:
        pending.delete()

        raise ValueError(
            "PIN has expired. Please request a new one."
        )

    if pending.pin != pin:
        raise ValueError(
            "Incorrect PIN. Please try again."
        )

    return pending


def complete_pending_registration(
    pending,
    name: str,
    password: str,
) -> tuple:
    """
    Create tenant + admin, set credentials, reload with
    roles/permissions, then delete pending registration.

    All tenant-scoped ORM work happens synchronously inside
    schema_context to avoid async/thread-local schema leakage.
    """
    user_info = {
        "email":       pending.email,
        "name":        "",
        "provider_id": None,
        "picture_url": None,
    }

    employee, schema_name = create_new_tenant_and_admin(
        user_info=user_info,
        business_name=pending.business_name,
        set_unusable_password=False,
    )

    with schema_context(schema_name):

        employee.name = name
        employee.set_password(password)

        employee.save(update_fields=["name", "password"])

        employee = (
            type(employee).objects
            .prefetch_related("roles__permissions")
            .get(pk=employee.pk)
        )

    pending.delete()

    logger.info(
        "Completed pending registration for %s",
        pending.email,
    )

    return employee, schema_name