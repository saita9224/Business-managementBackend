import strawberry
from strawberry.extensions import SchemaExtension
from strawberry.types import ExecutionContext
import jwt
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()


class JWTMiddleware(SchemaExtension):

    def on_request_start(self):
        context = self.execution_context.context

        # Initialize context.user (Django style)
        setattr(context, "user", None)

        request = context.request
        auth = request.headers.get("Authorization")

        if not auth:
            return  # No token provided

        try:
            prefix, token = auth.split(" ")
            if prefix.lower() != "bearer":
                return

            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user = User.objects.get(id=payload["user_id"])

            # Attach authenticated user
            setattr(context, "user", user)

        except Exception:
            # On any token/DB error → unauthenticated
            setattr(context, "user", None)
