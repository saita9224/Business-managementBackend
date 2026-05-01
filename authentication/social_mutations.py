# authentication/social_mutations.py

"""
GraphQL mutation for social auth.
Lives in the PUBLIC schema endpoint so unauthenticated
users can call it before they have a tenant subdomain.

Auth paths
──────────
Admin (new):      socialAuth → creates Business + Employee + SocialAccount → JWT
Admin (returning): socialAuth → finds SocialAccount → JWT
Employee:         login mutation (email + password) — handled in authentication/mutations.py

Optional future path for employees:
  Employee signs in with Google/Facebook for the first time →
  email from OAuth matches admin-pre-created Employee →
  SocialAccount is created and linked automatically.
  Subsequent logins use the SocialAccount (no password needed).
"""

import re
import strawberry
from graphql import GraphQLError
from asgiref.sync import sync_to_async
from django_tenants.utils import schema_context

from authentication.services import create_jwt_token
from authentication.social import verify_social_token


# ======================================================
# RESPONSE TYPE
# ======================================================

@strawberry.type
class SocialAuthPayload:
    token:       str
    user_id:     int
    name:        str
    email:       str
    roles:       list[str]
    permissions: list[str]
    schema_name: str   # subdomain the app must use for all future requests
    is_new_user: bool  # true when a new Business was just created


# ======================================================
# HELPERS
# ======================================================

def _slugify(text: str) -> str:
    """Convert a business name to a safe PostgreSQL schema name."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "_", slug)
    slug = re.sub(r"^-+|-+$", "", slug)
    if slug and slug[0].isdigit():
        slug = "b_" + slug
    return slug[:50]


def _unique_schema_name(base: str) -> str:
    """Append a counter if the schema name is already taken."""
    from tenants.models import Business

    name, counter = base, 1
    while Business.objects.filter(schema_name=name).exists():
        name = f"{base}_{counter}"
        counter += 1
    return name


# ======================================================
# LOOKUP — checks SocialAccount first, then email fallback
# ======================================================

def _find_existing_user(provider: str, provider_id: str, email: str):
    """
    Search every tenant schema for a match. Two-stage lookup:

    Stage 1 — SocialAccount match (provider + provider_id):
        The normal path for any user who has signed in with
        this provider before. Fast and unambiguous.

    Stage 2 — Email match (fallback):
        Catches the case where an admin pre-created an Employee
        with an email address, and this is the employee's first
        OAuth sign-in. The email from the OAuth token must exactly
        match the email the admin registered — this is the strict
        policy the admin chose.

        On a successful email match, a SocialAccount is created
        automatically so Stage 1 handles all future logins.

    Returns (employee, schema_name, is_new_social_link) or (None, None, False).
    """
    from tenants.models import Business
    from employees.models import Employee, SocialAccount

    for tenant in Business.objects.exclude(schema_name="public"):
        with schema_context(tenant.schema_name):

            # ── Stage 1: SocialAccount lookup ─────────────────────
            try:
                account = (
                    SocialAccount.objects
                    .select_related("employee")
                    .get(provider=provider, provider_id=provider_id)
                )
                return account.employee, tenant.schema_name, False
            except SocialAccount.DoesNotExist:
                pass

            # ── Stage 2: Email fallback for pre-created employees ──
            if email:
                try:
                    employee = (
                        Employee.objects
                        .get(email__iexact=email, is_active=True)
                    )

                    # Auto-link: create SocialAccount so next login
                    # is resolved by Stage 1 without the email scan.
                    SocialAccount.objects.create(
                        employee=employee,
                        provider=provider,
                        provider_id=provider_id,
                        email=email,
                        name=employee.name,
                        picture_url=None,
                    )

                    return employee, tenant.schema_name, True

                except Employee.DoesNotExist:
                    pass

    return None, None, False


# ======================================================
# CREATE — new admin registering a brand-new Business
# ======================================================

def _create_new_tenant_and_admin(provider: str, user_info: dict, business_name: str):
    """
    Create a new Business (PostgreSQL schema), an Employee with the
    Admin role, and a linked SocialAccount — all in one atomic flow.

    Only called when no existing user was found AND business_name
    was supplied. Employees are never created this way — they are
    created by the admin via the existing employee management mutations.

    Returns (employee, schema_name).
    """
    from tenants.models import Business, Domain
    from employees.models import Employee, Role, SocialAccount
    from django.db import transaction

    # ── 1. Create the Business (triggers auto_create_schema) ──────
    base_slug   = _slugify(business_name)
    schema_name = _unique_schema_name(base_slug)

    business = Business(schema_name=schema_name, name=business_name)
    business.save()  # PG schema created + tenant migrations run automatically

    # ── 2. Create domain (schema_name used as subdomain) ──────────
    Domain.objects.create(
        tenant=business,
        domain=f"{schema_name}.localhost",  # replace with real domain in production
        is_primary=True,
    )

    # ── 3. Inside the new schema: Employee + Admin role + SocialAccount
    with schema_context(schema_name):
        with transaction.atomic():
            admin_role, _ = Role.objects.get_or_create(name="Admin")

            # Use email from OAuth; fall back to a synthetic address if
            # the provider didn't return one (rare but possible).
            email = (
                user_info["email"]
                or f"{provider}_{user_info['provider_id']}@noemail.local"
            )

            employee = Employee(
                name=user_info["name"] or "Admin",
                email=email,
                is_active=True,
            )
            # Admin has no password — they always sign in via OAuth.
            # Employees use email + password set by the admin.
            employee.set_unusable_password()
            employee.save()
            employee.roles.add(admin_role)

            SocialAccount.objects.create(
                employee=employee,
                provider=provider,
                provider_id=user_info["provider_id"],
                email=email,
                name=user_info["name"] or "",
                picture_url=user_info.get("picture_url"),
            )

    return employee, schema_name


# ======================================================
# PAYLOAD BUILDER
# ======================================================

def _build_payload(
    employee,
    schema_name: str,
    is_new_user: bool,
) -> SocialAuthPayload:
    token = create_jwt_token(employee)

    roles = [role.name for role in employee.roles.all()]
    permissions = list({
        perm.code
        for role in employee.roles.all()
        for perm in role.permissions.all()
    })

    return SocialAuthPayload(
        token=token,
        user_id=employee.id,
        name=employee.name,
        email=employee.email,
        roles=roles,
        permissions=permissions,
        schema_name=schema_name,
        is_new_user=is_new_user,
    )


# ======================================================
# MUTATION
# ======================================================

@strawberry.type
class SocialAuthMutation:

    @strawberry.mutation
    async def social_auth(
        self,
        provider:      str,
        token:         str,
        business_name: str | None = None,
    ) -> SocialAuthPayload:
        """
        Authenticate via Google or Facebook.

        Args:
            provider:
                "google" or "facebook"

            token:
                id_token (Google) or access_token (Facebook)
                obtained by the mobile app directly from the provider SDK.

            business_name:
                Required only when a brand-new admin is registering
                their Business for the first time.
                Ignored for all returning users (admin or employee).

        Behaviour matrix:
            SocialAccount exists          → log in (admin or employee, doesn't matter)
            No SocialAccount, email match → auto-link OAuth to existing Employee, log in
            No match at all + business_name provided → create new Business + admin
            No match at all + no business_name       → error (unknown user)
        """

        # ── Verify token with provider ─────────────────────────────
        try:
            user_info = await verify_social_token(provider, token)
        except ValueError as exc:
            raise GraphQLError(str(exc))

        provider_id = user_info["provider_id"]
        email       = user_info.get("email", "")

        # ── Look up existing user (SocialAccount or email match) ───
        employee, schema_name, was_linked = await sync_to_async(
            _find_existing_user
        )(provider, provider_id, email)

        if employee:
            # Reload with roles + permissions inside the correct schema
            with schema_context(schema_name):
                employee = await sync_to_async(
                    lambda: type(employee).objects
                    .prefetch_related("roles__permissions")
                    .get(pk=employee.pk)
                )()
            # is_new_user=False for all returning users and auto-linked employees
            return _build_payload(employee, schema_name, is_new_user=False)

        # ── No existing user found ─────────────────────────────────
        # Only admins register new businesses. Employees cannot
        # self-register — they must be created by an admin first.
        if not business_name or not business_name.strip():
            raise GraphQLError(
                "No account found for this email. "
                "If you are an employee, ask your admin to create your account. "
                "If you are registering a new business, provide business_name."
            )

        # ── Create new Business + admin ────────────────────────────
        employee, schema_name = await sync_to_async(
            _create_new_tenant_and_admin
        )(provider, user_info, business_name.strip())

        with schema_context(schema_name):
            employee = await sync_to_async(
                lambda: type(employee).objects
                .prefetch_related("roles__permissions")
                .get(pk=employee.pk)
            )()

        return _build_payload(employee, schema_name, is_new_user=True)