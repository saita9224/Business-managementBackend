# tenants/models.py

from django_tenants.models import TenantMixin, DomainMixin
from django.db import models
from django.contrib.auth.hashers import make_password, check_password


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

    Lives in the public schema — completely separate from the
    per-tenant Employee model. Created once via management command,
    never via GraphQL.

    SuperAdmin never logs in through the tenant endpoint. It has
    its own JWT with no schema_name — it uses schema_context
    explicitly when it needs to enter a tenant schema.
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