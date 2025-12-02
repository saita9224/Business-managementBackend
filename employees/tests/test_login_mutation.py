import pytest
from employees.models import Employee
from django.contrib.auth.hashers import make_password


@pytest.mark.django_db
def test_login_success(client):
    Employee.objects.create(
        name="Admin",
        email="admin@example.com",
        password=make_password("Admin123!")
    )

    query = """
    mutation {
      login(email: "admin@example.com", password: "Admin123!") {
        token
        userId
        name
      }
    }
    """

    response = client.post("/graphql/", {"query": query})
    data = response.json()["data"]["login"]

    assert data["token"] is not None
    assert data["name"] == "Admin"


@pytest.mark.django_db
def test_login_invalid_password(client):
    Employee.objects.create(
        name="Admin",
        email="admin@example.com",
        password=make_password("Admin123!")
    )

    query = """
    mutation {
      login(email: "admin@example.com", password: "Wrong") {
        token
      }
    }
    """

    response = client.post("/graphql/", {"query": query})
    assert "errors" in response.json()
