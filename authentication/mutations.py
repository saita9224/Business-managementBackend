import strawberry
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from strawberry.types import Info
from .services import create_jwt_token

@strawberry.type
class AuthPayload:
    user_id: int
    username: str
    token: str

@strawberry.type
class AuthMutation:

    @strawberry.mutation
    def signup(self, username: str, password: str) -> AuthPayload:
        user = User.objects.create_user(username=username, password=password)
        token = create_jwt_token(user)
        return AuthPayload(user_id=user.id, username=user.username, token=token)

    @strawberry.mutation
    def login(self, username: str, password: str) -> AuthPayload:
        user = authenticate(username=username, password=password)
        if not user:
            raise Exception("Invalid username or password")

        token = create_jwt_token(user)
        return AuthPayload(user_id=user.id, username=user.username, token=token)
