# backend/middleware.py

import logging
from strawberry.extensions import SchemaExtension
from authentication.services import decode_jwt_token

logger = logging.getLogger(__name__)


class JWTMiddleware(SchemaExtension):

    async def on_request_start(self):
        """
        Async version – required because decode_jwt_token is async
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

        # Default user
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
                        user = await decode_jwt_token(token)

                        if user:
                            set_attr(context, "user", user)
                            logger.debug(f"Authenticated user: {user.email}")
                        else:
                            logger.debug("Invalid or expired JWT token")

        logger.debug("JWT middleware completed successfully")