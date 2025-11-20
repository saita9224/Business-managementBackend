import jwt
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth.models import User

SECRET = settings.SECRET_KEY
ALGORITHM = "HS256"

def create_jwt_token(user: User):
    payload = {
        "user_id": user.id,
        "exp": datetime.utcnow() + timedelta(days=1),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)

def decode_jwt_token(token: str):
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        return User.objects.get(id=payload["user_id"])
    except Exception:
        return None
