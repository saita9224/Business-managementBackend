# authentication/services.py

import jwt
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.utils import timezone

from employees.models import Employee


JWT_SECRET = getattr(settings, "JWT_SECRET", settings.SECRET_KEY)
ALGORITHM = getattr(settings, "JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRES = getattr(
    settings, "JWT_ACCESS_EXPIRES_SECONDS", 3600  # 1 hour
)


# ======================================================
# CREATE JWT TOKEN
# ======================================================
def create_jwt_token(employee: Employee, expires_in: int = ACCESS_TOKEN_EXPIRES) -> str:
    now = timezone.now()

    payload = {
        "user_id": employee.id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }

    token = jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

    # PyJWT < 2.0 returns bytes
    if isinstance(token, bytes):
        token = token.decode("utf-8")

    return token


# ======================================================
# DECODE JWT TOKEN
# ======================================================
def decode_jwt_token(token: str) -> Optional[Employee]:
    from jwt import ExpiredSignatureError, InvalidTokenError, DecodeError

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")

        if not user_id:
            return None

        employee = Employee.objects.get(id=user_id)

        if not employee.is_active:
            return None

        return employee

    except (ExpiredSignatureError, InvalidTokenError, DecodeError, Employee.DoesNotExist):
        return None
