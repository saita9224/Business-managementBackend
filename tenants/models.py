# tenants/models.py

from django_tenants.models import TenantMixin, DomainMixin
from django.db import models
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from datetime import timedelta


class Business(TenantMixin):
    name       = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    auto_create_schema = True

    def __str__(self):
        return self.name


class Domain(DomainMixin):
    pass


# ======================================================
# SUPER ADMIN — lives in the public schema
# ======================================================

class SuperAdmin(models.Model):
    """
    Platform-level administrator with access to all tenants.
    Created once via management command, never via GraphQL.
    """

    email      = models.EmailField(unique=True, db_index=True)
    password   = models.CharField(max_length=255)
    name       = models.CharField(max_length=100)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'tenants'
        verbose_name = 'Super Admin'

    def set_password(self, raw_password: str) -> None:
        self.password = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password(raw_password, self.password)

    def __str__(self):
        return f"SuperAdmin({self.email})"


# ======================================================
# PENDING REGISTRATION — lives in the public schema
# ======================================================

class PendingRegistration(models.Model):
    """
    Temporary record created when a new admin requests registration
    via the email+password path.

    Moved here from authentication/models.py so it lives cleanly
    in a SHARED_APP with no tenant conflict.

    Lifecycle:
        created  → requestRegistration mutation
        verified → verifyRegistration mutation (record deleted)
        expired  → detected on verify attempt (record deleted)
        resent   → requestRegistration called again (old record replaced)

    Google OAuth admins never touch this model — they are verified
    by Google directly and bypass this flow entirely.
    """

    email         = models.EmailField(unique=True, db_index=True)
    business_name = models.CharField(max_length=200)
    pin           = models.CharField(max_length=6)
    created_at    = models.DateTimeField(auto_now_add=True)
    expires_at    = models.DateTimeField()

    class Meta:
        app_label = 'tenants'

    def save(self, *args, **kwargs):
        if not self.pk:
            self.expires_at = timezone.now() + timedelta(minutes=30)
        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"PendingRegistration({self.email}, expires={self.expires_at})"