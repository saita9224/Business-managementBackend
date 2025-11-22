# authentication/services.py

import jwt
from datetime import datetime, timedelta
from django.conf import settings

from employees.models import Employee   # ✅ Correct model

SECRET = settings.SECRET_KEY
ALGORITHM = "HS256"


def create_jwt_token(employee: Employee):
    payload = {
        "user_id": employee.id,
        "exp": datetime.utcnow() + timedelta(days=1),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def decode_jwt_token(token: str):
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        return Employee.objects.get(id=payload["user_id"])
    except Exception:
        return None
