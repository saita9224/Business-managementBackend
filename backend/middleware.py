# backend/middleware.py

import logging
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from django.conf import settings
from django.contrib.auth import get_user_model

import strawberry
from strawberry.extensions import SchemaExtension

logger = logging.getLogger(__name__)
User = get_user_model()


class JWTMiddleware(SchemaExtension):

    def on_request_start(self):
        context = self.execution_context.context
        setattr(context, "user", None)

        request = getattr(context, "request", None)
        if request is None:
            return

        auth_header = request.headers.get("Authorization")
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

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")

            if not user_id:
                logger.debug("Token missing user_id")
                return

            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                logger.info("User does not exist: id=%s", user_id)
                return

            setattr(context, "user", user)

        except ExpiredSignatureError:
            logger.info("Expired JWT token")
        except InvalidTokenError:
            logger.info("Invalid JWT token")
        except Exception as exc:
            logger.exception("Unexpected JWT error: %s", exc)
