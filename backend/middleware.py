# backend/middleware.py

import logging
from strawberry.extensions import SchemaExtension
from django.db import connection
from authentication.services import decode_jwt_token

logger = logging.getLogger(__name__)


class JWTMiddleware(SchemaExtension):

    async def on_operation(self):
        """
        Runs before and after every GraphQL operation.
        Must yield to allow execution to proceed.

        Also derives and activates the tenant schema from the JWT's
        schema_name claim (set at login/registration -- see
        authentication/services.py create_jwt_token), so clients no
        longer need to send X-Tenant on authenticated requests. The
        JWT already carries everything needed to route the request
        to the correct schema.

        XTenantMiddleware / X-Tenant header still work unchanged for
        requests without a JWT (local tooling, scripts) since Django
        middleware runs before this extension and may already have
        set a non-public schema -- in that case we don't override it.
        """

        context = self.execution_context.context

        def set_attr(ctx, key, value):
            if isinstance(ctx, dict):
                ctx[key] = value
            else:
                setattr(ctx, key, value)

        def get_attr(ctx, key, default=None):
            if isinstance(ctx, dict):
                return ctx.get(key, default)
            return getattr(ctx, key, default)

        # Default to unauthenticated
        set_attr(context, "user", None)

        request = get_attr(context, "request")

        schema_switched = False

        if request:
            auth_header = (
                request.headers.get("Authorization")
                or request.META.get("HTTP_AUTHORIZATION")
            )

            if auth_header:
                parts = auth_header.split()

                if len(parts) == 2:
                    prefix, token = parts

                    if prefix.lower() == "bearer":
                        # If Django middleware (X-Tenant / subdomain)
                        # already resolved a non-public tenant, respect
                        # it and just verify the JWT matches. Otherwise
                        # we're still on public -- let the JWT itself
                        # decide the schema.
                        current_schema = getattr(
                            connection, "schema_name", None
                        )

                        if current_schema and current_schema != "public":
                            expected_schema_name = current_schema
                        else:
                            expected_schema_name = None

                        user = await decode_jwt_token(
                            token,
                            expected_schema_name=expected_schema_name,
                        )

                        if user:
                            set_attr(context, "user", user)
                            logger.debug(f"Authenticated: {user.email}")

                            # Activate the tenant schema for the rest
                            # of this operation, if not already active.
                            if (
                                current_schema == "public"
                                or current_schema is None
                            ):
                                from asgiref.sync import sync_to_async

                                jwt_schema_name = getattr(
                                    user, "_jwt_schema_name", None
                                )
                                # decode_jwt_token doesn't currently
                                # return the schema_name alongside the
                                # user -- see services.py change below.
                                if jwt_schema_name:
                                    await sync_to_async(
                                        connection.set_schema
                                    )(jwt_schema_name)
                                    schema_switched = True
                        else:
                            logger.debug("Invalid or expired token")

        yield  # 👈 resolvers execute here

        if schema_switched:
            from asgiref.sync import sync_to_async
            await sync_to_async(connection.set_schema_to_public)()