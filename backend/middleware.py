import jwt
from django.contrib.auth.models import User
from django.conf import settings
from jwt import ExpiredSignatureError, InvalidSignatureError, DecodeError

SECRET = settings.SECRET_KEY
ALGORITHM = "HS256"


class JWTMiddleware:
    async def resolve(self, _next, root, info, *args, **kwargs):
        request = info.context["request"]

        # Default if not authenticated
        request.user = None

        auth_header = request.headers.get("Authorization")

        if auth_header:
            try:
                prefix, token = auth_header.split(" ")

                if prefix.lower() == "bearer":
                    payload = jwt.decode(
                        token,
                        SECRET,
                        algorithms=[ALGORITHM],
                        options={"verify_aud": False}  # prevents weird audience errors
                    )
                    request.user = User.objects.get(id=payload["user_id"])

            except (ExpiredSignatureError, InvalidSignatureError, DecodeError):
                request.user = None  # token invalid/expired

            except User.DoesNotExist:
                request.user = None  # token valid but user deleted

            except Exception:
                request.user = None  # fallback safe

        return await _next(root, info, *args, **kwargs)
