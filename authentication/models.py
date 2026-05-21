# authentication/models.py

"""
Authentication app models.

PendingRegistration has been moved to tenants/models.py because
it lives in the public schema and tenants is a purely SHARED_APP
with no conflict. generate_pin() stays here as it is used by
both authentication services and employees services.
"""

import random


def generate_pin() -> str:
    """
    Generate a cryptographically adequate 6-digit PIN.
    Uses SystemRandom which draws from the OS entropy pool,
    making it suitable for security-sensitive purposes.
    """
    return f"{random.SystemRandom().randint(0, 999999):06d}"