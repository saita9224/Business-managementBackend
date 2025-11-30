# authentication/services.py

import jwt
from datetime import datetime, timedelta
from django.conf import settings

from employees.models import Employee

SECRET = settings.SECRET_KEY
ALGORITHM = "HS256"


def create_jwt_token(employee: Employee):
    """
    Creates a JWT containing the employee ID and expiration.
    """
    payload = {
        "user_id": employee.id,
        "exp": datetime.utcnow() + timedelta(days=1),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def decode_jwt_token(token: str):
    """
    Decode JWT and return Employee or None.
    """
    from jwt import ExpiredSignatureError, InvalidTokenError

    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        return Employee.objects.get(id=payload["user_id"])

    except (ExpiredSignatureError, InvalidTokenError, Employee.DoesNotExist):
        return None
