# authentication/models.py

"""
PendingRegistration lives in the PUBLIC schema.
It holds unverified admin registrations until the PIN
is confirmed, at which point the Business schema is created
and this record is deleted.
"""

import random
from django.db import models
from django.utils import timezone
from datetime import timedelta


def generate_pin() -> str:
    """Generate a cryptographically adequate 6-digit PIN."""
    return f"{random.SystemRandom().randint(0, 999999):06d}"


class PendingRegistration(models.Model):
    """
    Temporary record created when a new admin requests registration.
    Deleted immediately after successful PIN verification.
    Lives in the public schema (not a tenant app).
    """

    email         = models.EmailField(unique=True, db_index=True)
    business_name = models.CharField(max_length=200)
    pin           = models.CharField(max_length=6)
    created_at    = models.DateTimeField(auto_now_add=True)
    expires_at    = models.DateTimeField()

    # Google id_token stored temporarily so verifyRegistration
    # can proceed with Google-authenticated registration too.
    # Null for plain email registrations.
    google_id_token = models.TextField(blank=True, null=True)

    class Meta:
        app_label = 'authentication'

    def save(self, *args, **kwargs):
        if not self.pk:
            self.expires_at = timezone.now() + timedelta(minutes=30)
        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"PendingRegistration({self.email}, expires={self.expires_at})"