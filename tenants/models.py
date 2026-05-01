# tenants/models.py
from django_tenants.models import TenantMixin, DomainMixin
from django.db import models

class Business(TenantMixin):
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    auto_create_schema = True  # django-tenants creates the PG schema automatically

class Domain(DomainMixin):
    pass