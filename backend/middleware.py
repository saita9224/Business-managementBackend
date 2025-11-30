# backend/middleware.py (improved)

import logging
from django.conf import settings
from django.contrib.auth import get_user_model
import strawberry
from strawberry.extensions import SchemaExtension

from authentication.services import decode_jwt_token

logger = logging.getLogger(__name__)
User = get_user_model()


class JWTMiddleware(SchemaExtension):
    def on_request_start(self):
        # execution_context.context may be a dict or an object
        context = self.execution_context.context

        # normalize: allow attribute or mapping access
        def set_user_on_context(ctx, user):
            try:
                setattr(ctx, "user", user)
            except Exception:
                try:
                    ctx["user"] = user
                except Exception:
                    # final fallback: do nothing
                    logger.debug("Could not set user on context object")

        set_user_on_context(context, None)

        request = getattr(context, "request", None) or (context.get("request") if isinstance(context, dict) else None)
        if request is None:
            return

        auth_header = request.headers.get("Authorization") or request.META.get("HTTP_AUTHORIZATION")
        if not auth_header:
            return

        parts = auth_header.split()
        if len(parts) != 2:
            logger.debug("Malformed Authorization header")
            return

        prefix, token = parts
        if prefix.lower() != "bearer":
            logger.debug("Authorization header missing Bearer prefix")
            return

        user = decode_jwt_token(token)  # centralized decode (returns user or None)
        if user:
            set_user_on_context(context, user)
        else:
            logger.debug("JWT did not decode to a valid user")
