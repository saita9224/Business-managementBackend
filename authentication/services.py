# authentication/services.py (improved)

import jwt
from datetime import datetime, timedelta
from django.conf import settings
from typing import Optional

from employees.models import Employee

JWT_SECRET = getattr(settings, "JWT_SECRET", settings.SECRET_KEY)
ALGORITHM = getattr(settings, "JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRES = getattr(settings, "JWT_ACCESS_EXPIRES_SECONDS", 3600)  # 1 hour

def create_jwt_token(employee: Employee, expires_in: int = ACCESS_TOKEN_EXPIRES) -> str:
    now = datetime.utcnow()
    payload = {
        "user_id": employee.id,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
        # Optional claims you can add:
        # "iss": "your-app-name",
        # "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)
    # pyjwt v1 returns bytes, so ensure str
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token

def decode_jwt_token(token: str) -> Optional[Employee]:
    from jwt import ExpiredSignatureError, InvalidTokenError, DecodeError
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            return None
        return Employee.objects.get(id=user_id)
    except (ExpiredSignatureError, InvalidTokenError, DecodeError, Employee.DoesNotExist):
        return None
