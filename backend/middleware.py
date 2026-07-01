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
                        tenant = getattr(request, "tenant", None)
                        expected_schema_name = (
                            getattr(tenant, "schema_name", None)
                            or getattr(connection, "schema_name", None)
                        )
                        if expected_schema_name == "public":
                            expected_schema_name = None

                        user = await decode_jwt_token(
                            token,
                            expected_schema_name=expected_schema_name,
                        )

                        if user:
                            set_attr(context, "user", user)
                            logger.debug(f"Authenticated: {user.email}")
                        else:
                            logger.debug("Invalid or expired token")

        yield  # 👈 resolvers execute here
