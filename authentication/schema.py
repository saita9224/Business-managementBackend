import strawberry
from .mutations import AuthMutation

@strawberry.type
class AuthQuery:
    # placeholder query (not needed yet)
    hello_auth: str = "Auth system ready"

AuthMutationType = AuthMutation
