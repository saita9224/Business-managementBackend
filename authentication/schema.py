# authentication/schema.py

import strawberry
from .mutations import AuthMutation


@strawberry.type
class AuthQuery:
    status: str = "Authentication system operational"


@strawberry.type
class AuthMutationType(AuthMutation):
    pass
