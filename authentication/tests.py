import jwt
from django.conf import settings
from django.test import SimpleTestCase

from authentication.models import generate_pin
from authentication.services import (
    ALGORITHM,
    JWT_SECRET,
    _slugify,
    create_jwt_token,
    create_super_admin_jwt,
)


class AuthenticationUtilityTests(SimpleTestCase):
    def test_generate_pin_returns_six_digits(self):
        pin = generate_pin()

        self.assertEqual(len(pin), 6)
        self.assertTrue(pin.isdigit())

    def test_slugify_normalizes_business_names_for_schema_names(self):
        self.assertEqual(_slugify(" My Hotel & Bar "), "my_hotel_bar")
        self.assertEqual(_slugify("123 Cafe"), "b_123_cafe")

    def test_employee_jwt_contains_schema_and_employee_role(self):
        employee = type("EmployeeStub", (), {"id": 42})()

        token = create_jwt_token(employee, "demo_schema", expires_in=60)
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])

        self.assertEqual(payload["user_id"], 42)
        self.assertEqual(payload["schema_name"], "demo_schema")
        self.assertEqual(payload["role"], "employee")

    def test_super_admin_jwt_uses_superadmin_claims(self):
        admin = type("AdminStub", (), {"id": 7})()

        token = create_super_admin_jwt(admin, expires_in=60)
        payload = jwt.decode(
            token,
            getattr(settings, "JWT_SECRET", settings.SECRET_KEY),
            algorithms=[ALGORITHM],
        )

        self.assertEqual(payload["super_admin_id"], 7)
        self.assertEqual(payload["role"], "superadmin")
