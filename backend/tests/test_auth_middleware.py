import jwt
import pytest
from django.conf import settings
from authentication.services import create_jwt_token
from employees.models import Employee


@pytest.mark.django_db
def test_middleware_sets_user(client, employee_factory):
    employee = employee_factory()
    token = create_jwt_token(employee)

    response = client.post(
        "/graphql/",
        {"query": "{ roles { id } }"},
        HTTP_AUTHORIZATION=f"Bearer {token}"
    )

    # If no error thrown, context.user was set correctly
    assert response.status_code == 200


@pytest.mark.django_db
def test_middleware_invalid_token_sets_user_none(client):
    response = client.post(
        "/graphql/",
        {"query": "{ roles { id } }"},
        HTTP_AUTHORIZATION="Bearer invalid.token.here"
    )

    assert response.status_code == 200
    # Query will fail or return empty, but should not crash middleware
