# authentication/social_mutations.py

"""
Google Sign-In mutation.

All business logic lives in authentication/services.py.
This file is intentionally thin — it only handles:
  - receiving the GraphQL arguments
  - calling services
  - returning the typed payload
"""

import strawberry
from graphql import GraphQLError
from asgiref.sync import sync_to_async
from django_tenants.utils import schema_context

from authentication.social import verify_google_token
from authentication.services import (
    find_existing_google_user,
    create_new_tenant_and_admin,
    build_auth_payload,
)


@strawberry.type
class GoogleAuthPayload:
    token:       str
    user_id:     int
    name:        str
    email:       str
    roles:       list[str]
    permissions: list[str]
    schema_name: str   # subdomain the app uses for all future requests
    is_new_user: bool  # true when a brand-new Business was just created


@strawberry.type
class SocialAuthMutation:

    @strawberry.mutation
    async def google_auth(
        self,
        id_token:      str,
        business_name: str | None = None,
    ) -> GoogleAuthPayload:
        """
        Authenticate via Google Sign-In.

        Args:
            id_token:      Google id_token from expo-auth-session.
            business_name: Required only when registering a new Business.
                           Omit for all returning users.

        Behaviour:
            SocialAccount found           → log in
            No SocialAccount, email match → auto-link + log in
            No match + businessName       → create Business + admin + log in
            No match + no businessName    → error (contact admin)
        """

        # 1. Verify token with Google's servers
        try:
            user_info = await verify_google_token(id_token)
        except ValueError as exc:
            raise GraphQLError(str(exc))

        google_id = user_info["provider_id"]
        email     = user_info.get("email", "")

        # 2. Look for an existing user across all tenant schemas
        employee, schema_name = await sync_to_async(
            find_existing_google_user
        )(google_id, email)

        if employee:
            # Reload with roles + permissions inside the correct schema
            with schema_context(schema_name):
                employee = await sync_to_async(
                    lambda: type(employee).objects
                    .prefetch_related("roles__permissions")
                    .get(pk=employee.pk)
                )()
            data = build_auth_payload(employee, schema_name, is_new_user=False)
            return GoogleAuthPayload(**data)

        # 3. No existing user — register a new Business
        if not business_name or not business_name.strip():
            raise GraphQLError(
                "No account found for this Google account. "
                "If you are an employee, ask your admin to create your account first. "
                "If you are registering a new business, provide businessName."
            )

        employee, schema_name = await sync_to_async(
            create_new_tenant_and_admin
        )(user_info, business_name.strip())

        # Reload with relations
        with schema_context(schema_name):
            employee = await sync_to_async(
                lambda: type(employee).objects
                .prefetch_related("roles__permissions")
                .get(pk=employee.pk)
            )()

        data = build_auth_payload(employee, schema_name, is_new_user=True)
        return GoogleAuthPayload(**data)