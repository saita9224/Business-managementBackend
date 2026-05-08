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
"""

import re
import jwt
import logging
from datetime import timedelta
from typing import Optional

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
    schema_name is embedded so decode_jwt_token can activate the
    correct tenant schema without needing the request subdomain.
    """
    now = timezone.now()

    payload = {
        "user_id":     employee.id,
        "schema_name": schema_name,
        "role":        "employee",   # distinguishes from superadmin tokens
        "iat":         int(now.timestamp()),
        "exp":         int((now + timedelta(seconds=expires_in)).timestamp()),
    }

    token = jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

    if isinstance(token, bytes):
        token = token.decode("utf-8")

    return token


async def decode_jwt_token(token: str):
    """
    Decode an employee JWT and return the matching Employee,
    or None on any failure.

    Explicitly rejects SuperAdmin tokens (role='superadmin')
    so they cannot be used against the tenant endpoint.
    """
    from jwt import ExpiredSignatureError, InvalidTokenError, DecodeError
    from employees.models import Employee

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])

        # Reject superadmin tokens on the employee decoder
        if payload.get("role") == "superadmin":
            logger.debug("Employee decoder rejected superadmin token")
            return None

        user_id     = payload.get("user_id")
        schema_name = payload.get("schema_name")

        if not user_id or not schema_name:
            logger.debug("JWT missing user_id or schema_name")
            return None

        with schema_context(schema_name):
            employee = await sync_to_async(Employee.objects.get)(id=user_id)

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
# SUPER ADMIN JWT — separate from employee JWTs
# ======================================================

def create_super_admin_jwt(
    admin,
    expires_in: int = ACCESS_TOKEN_EXPIRES,
) -> str:
    """
    Create a JWT for the SuperAdmin.
    No schema_name — SuperAdmin is not scoped to any tenant.
    role='superadmin' distinguishes these tokens from employee tokens.
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
    Explicitly rejects employee tokens (role != 'superadmin').
    Returns the SuperAdmin instance or None.
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
# AUTH PAYLOAD — shared by all employee auth paths
# ======================================================

def build_auth_payload(
    employee,
    schema_name: str,
    is_new_user: bool = False,
) -> dict:
    """
    Shared by login, googleAuth, and verifyRegistration so all
    employee auth paths return consistent data.
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
# GOOGLE AUTH — tenant lookup
# ======================================================

def find_existing_google_user(google_id: str, email: str):
    """
    Search every tenant schema for a Google user.

    Stage 1 — SocialAccount match on google_id (normal path).
    Stage 2 — Email match fallback for employees pre-created by an
               admin before their first Google Sign-In. Auto-links
               a SocialAccount so Stage 1 handles all future logins.

    Returns (employee, schema_name) or (None, None).
    Sync — call via sync_to_async from mutations.
    """
    from tenants.models import Business
    from employees.models import Employee, SocialAccount

    for tenant in Business.objects.exclude(schema_name="public"):
        with schema_context(tenant.schema_name):

            # Stage 1
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
                        email, tenant.schema_name,
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
    Create a new Business (PostgreSQL schema auto-created + migrated),
    an Admin Employee, and optionally a SocialAccount.

    set_unusable_password=True  → Google OAuth admin (no password)
    set_unusable_password=False → email+password admin (caller sets password)

    Admin employees are always created with is_email_verified=True:
      - Google OAuth: Google already verified the email
      - Email+password: verified via PIN before this is called

    Returns (employee, schema_name).
    Sync — call via sync_to_async from mutations.
    """
    from tenants.models import Business, Domain
    from employees.models import Employee, Role, SocialAccount
    from django.db import transaction

    base_slug   = _slugify(business_name)
    schema_name = _unique_schema_name(base_slug)

    business = Business(schema_name=schema_name, name=business_name)
    business.save()  # triggers auto_create_schema

    Domain.objects.create(
        tenant=business,
        domain=f"{schema_name}.localhost",  # update to real domain in production
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
                is_email_verified=True,  # admins are always pre-verified
            )

            if set_unusable_password:
                employee.set_unusable_password()

            employee.save()
            employee.roles.add(admin_role)

            # Only create SocialAccount for Google OAuth admins
            if user_info.get("provider_id"):
                SocialAccount.objects.create(
                    employee=employee,
                    provider="google",
                    provider_id=user_info["provider_id"],
                    email=email,
                    name=user_info.get("name") or "",
                    picture_url=user_info.get("picture_url"),
                )

    logger.info("Created new tenant '%s' (schema: %s)", business_name, schema_name)
    return employee, schema_name


# ======================================================
# EMAIL+PASSWORD LOGIN — tenant lookup
# ======================================================

def find_employee_by_email(email: str):
    """
    Search every tenant schema for an Employee with this email.

    Returns (employee, schema_name) or (None, None).
    Sync — call via sync_to_async from mutations.
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
# PENDING REGISTRATION SERVICES
# ======================================================

def create_pending_registration(email: str, business_name: str) -> str:
    """
    Create or replace a PendingRegistration for this email.
    Returns the generated PIN. Replacing invalidates any old PIN.
    Sync — call via sync_to_async from mutations.
    """
    from authentication.models import PendingRegistration, generate_pin

    pin = generate_pin()

    PendingRegistration.objects.filter(email__iexact=email).delete()
    PendingRegistration.objects.create(
        email=email,
        business_name=business_name,
        pin=pin,
    )

    logger.info("Created pending registration for %s", email)
    return pin


def verify_pending_registration(email: str, pin: str):
    """
    Verify a PIN for a pending registration.

    Returns the PendingRegistration on success.
    Raises ValueError with a user-facing message on failure.
    Sync — call via sync_to_async from mutations.
    """
    from authentication.models import PendingRegistration

    try:
        pending = PendingRegistration.objects.get(email__iexact=email)
    except PendingRegistration.DoesNotExist:
        raise ValueError(
            "No pending registration found for this email. "
            "Please request a new PIN."
        )

    if pending.is_expired:
        pending.delete()
        raise ValueError("PIN has expired. Please request a new one.")

    if pending.pin != pin:
        raise ValueError("Incorrect PIN. Please try again.")

    return pending


def complete_pending_registration(pending) -> tuple:
    """
    Create the tenant and admin from a verified PendingRegistration,
    then delete the pending record.

    set_unusable_password=False because this is the email+password
    admin path — the caller sets the password after this returns.

    Returns (employee, schema_name).
    Sync — call via sync_to_async from mutations.
    """
    user_info = {
        "email":       pending.email,
        "name":        "",    # supplied by user at step 2
        "provider_id": None,  # no OAuth for this path
        "picture_url": None,
    }

    employee, schema_name = create_new_tenant_and_admin(
        user_info=user_info,
        business_name=pending.business_name,
        set_unusable_password=False,
    )

    pending.delete()
    logger.info("Completed pending registration for %s", pending.email)
    return employee, schema_name