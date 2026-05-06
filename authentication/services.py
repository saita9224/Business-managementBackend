# authentication/services.py

"""
JWT creation and decoding, plus all business logic that was
previously in social_mutations.py:

  - find_existing_google_user()
  - create_new_tenant_and_admin()
  - build_auth_payload()

Mutations stay thin — they call these services and return results.
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

JWT_SECRET = getattr(settings, "JWT_SECRET", settings.SECRET_KEY)
ALGORITHM  = getattr(settings, "JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRES = getattr(settings, "JWT_ACCESS_EXPIRES_SECONDS", 3600)


# ======================================================
# JWT — schema_name is embedded so every token is
# self-contained and tenant-aware on decode.
# ======================================================

def create_jwt_token(employee, schema_name: str, expires_in: int = ACCESS_TOKEN_EXPIRES) -> str:
    """
    Create a signed JWT for an authenticated employee.

    schema_name is embedded in the payload so decode_jwt_token
    can activate the correct tenant schema without needing the
    subdomain from the request (important for mobile clients
    that may call the public endpoint with a stored token).
    """
    now = timezone.now()

    payload = {
        "user_id":     employee.id,
        "schema_name": schema_name,   # ← tenant context baked into token
        "iat":         int(now.timestamp()),
        "exp":         int((now + timedelta(seconds=expires_in)).timestamp()),
    }

    token = jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

    if isinstance(token, bytes):
        token = token.decode("utf-8")

    return token


async def decode_jwt_token(token: str):
    """
    Decode a JWT and return the matching Employee, or None on any failure.

    Uses schema_name from the token payload to activate the correct
    tenant schema before querying — this makes the login mutation and
    JWTMiddleware fully multi-tenant aware regardless of which subdomain
    (or no subdomain) the request arrived on.
    """
    from jwt import ExpiredSignatureError, InvalidTokenError, DecodeError
    from employees.models import Employee

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])

        user_id     = payload.get("user_id")
        schema_name = payload.get("schema_name")

        if not user_id or not schema_name:
            logger.debug("JWT missing user_id or schema_name")
            return None

        # Activate the correct tenant schema before querying Employee.
        # Without this, the query hits whatever schema the current
        # request is scoped to — which may be wrong or public.
        with schema_context(schema_name):
            employee = await sync_to_async(Employee.objects.get)(id=user_id)

        if not employee.is_active:
            return None

        return employee

    except (ExpiredSignatureError, InvalidTokenError, DecodeError):
        logger.debug("JWT decode failed — expired or invalid")
        return None
    except Exception:
        # Catches Employee.DoesNotExist and any schema errors
        logger.debug("JWT decode failed — employee not found or schema error")
        return None


# ======================================================
# AUTH PAYLOAD — shared by both login paths
# ======================================================

def build_auth_payload(employee, schema_name: str, is_new_user: bool = False) -> dict:
    """
    Build the dict that both LoginPayload and GoogleAuthPayload
    are populated from. Centralised so both mutations return
    consistent data.
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
    Search every tenant schema for a Google user. Two-stage:

    Stage 1 — SocialAccount match on google_id (fast, normal path).
    Stage 2 — Email match fallback for employees whose account was
               pre-created by an admin before they first used Google
               Sign-In. Auto-links a SocialAccount on match so all
               future logins use Stage 1.

    Returns (employee, schema_name) or (None, None).
    This is a sync function — call via sync_to_async from mutations.
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
# GOOGLE AUTH — new tenant creation
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


def create_new_tenant_and_admin(user_info: dict, business_name: str):
    """
    Create a new Business (PostgreSQL schema auto-created),
    an Admin Employee, and a linked SocialAccount.

    Only called when no existing user was found AND business_name
    was provided. Employees are never created this way — only the
    first admin of a brand-new Business is created here.

    Returns (employee, schema_name).
    This is a sync function — call via sync_to_async from mutations.
    """
    from tenants.models import Business, Domain
    from employees.models import Employee, Role, SocialAccount
    from django.db import transaction

    base_slug   = _slugify(business_name)
    schema_name = _unique_schema_name(base_slug)

    # Business.save() triggers auto_create_schema — PostgreSQL schema
    # is created and all tenant migrations run automatically.
    business = Business(schema_name=schema_name, name=business_name)
    business.save()

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
                or f"google_{user_info['provider_id']}@noemail.local"
            )

            employee = Employee(
                name=user_info["name"] or "Admin",
                email=email,
                is_active=True,
            )
            employee.set_unusable_password()
            employee.save()
            employee.roles.add(admin_role)

            SocialAccount.objects.create(
                employee=employee,
                provider="google",
                provider_id=user_info["provider_id"],
                email=email,
                name=user_info["name"] or "",
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
    This is what makes the login mutation multi-tenant aware —
    the employee's schema is found by scanning, not assumed from
    the request subdomain.

    This is a sync function — call via sync_to_async from mutations.
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