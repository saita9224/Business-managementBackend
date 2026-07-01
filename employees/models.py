# employees/models.py

from django.db import models
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager,
)


# ======================================================
# EMPLOYEE MANAGER
# ======================================================
class EmployeeManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)
        employee = self.model(email=email, **extra_fields)
        employee.set_password(password)
        employee.save(using=self._db)
        return employee

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if not extra_fields.get("is_staff"):
            raise ValueError("Superuser must have is_staff=True")

        if not extra_fields.get("is_superuser"):
            raise ValueError("Superuser must have is_superuser=True")

        return self.create_user(email, password, **extra_fields)


# ======================================================
# EMPLOYEE MODEL (AUTH USER)
# ======================================================
class Employee(AbstractBaseUser, PermissionsMixin):
    name  = models.CharField(max_length=100)
    email = models.EmailField(unique=True, db_index=True)
    phone = models.CharField(max_length=20, blank=True, null=True)

    roles = models.ManyToManyField(
        "Role",
        through="EmployeeRole",
        related_name="employees",
        blank=True,
    )

    is_active = models.BooleanField(default=True)
    is_staff  = models.BooleanField(default=False)

    # ── Email verification ─────────────────────────────
    # Admins created via Google OAuth are verified immediately
    # (Google already verified the email).
    # Admins created via email+password are verified during
    # the requestRegistration → verifyRegistration flow before
    # the schema is even created, so they also start as True.
    # Employees created by an admin start as False and must
    # verify via the PIN sent in their welcome email.
    is_email_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    objects = EmployeeManager()

    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = ["name"]

    def __str__(self):
        return self.name

    def has_permission(self, permission, obj=None):
        """
        Alias required by Strawberry's AsyncGraphQLView which calls
        has_permission() internally. Delegates to Django's has_perm().
        """
        return self.has_perm(permission, obj)


# ======================================================
# ROLE MODEL
# ======================================================
class Role(models.Model):
    name        = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    permissions = models.ManyToManyField(
        "Permission",
        through="RolePermission",
        related_name="roles",
    )

    def __str__(self):
        return self.name


# ======================================================
# PERMISSION MODEL
# ======================================================
class Permission(models.Model):
    code        = models.CharField(max_length=150, unique=True)
    name        = models.CharField(max_length=150, unique=True)
    description = models.CharField(max_length=250)

    def __str__(self):
        return self.name


# ======================================================
# ROLE → PERMISSION
# ======================================================
class RolePermission(models.Model):
    role       = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("role", "permission")

    def __str__(self):
        return f"{self.role.name} → {self.permission.code}"


# ======================================================
# EMPLOYEE → ROLE
# ======================================================
class EmployeeRole(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    role     = models.ForeignKey(Role, on_delete=models.CASCADE)

    class Meta:
        indexes = [
            models.Index(fields=["employee", "role"]),
        ]
        unique_together = ("employee", "role")

    def __str__(self):
        return f"{self.employee.email} → {self.role.name}"


# ======================================================
# SOCIAL ACCOUNT
# ======================================================
class SocialAccount(models.Model):
    """
    Links a Google OAuth identity to an Employee.
    Stored in each tenant's schema alongside the Employee.
    """

    PROVIDER_GOOGLE  = "google"
    PROVIDER_CHOICES = [
        (PROVIDER_GOOGLE, "Google"),
    ]

    employee    = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="social_accounts",
    )
    provider    = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    provider_id = models.CharField(max_length=255)
    email       = models.EmailField()
    name        = models.CharField(max_length=150, blank=True)
    picture_url = models.URLField(blank=True, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("provider", "provider_id")
        indexes = [
            models.Index(fields=["provider", "provider_id"]),
        ]

    def __str__(self):
        return f"{self.provider}:{self.provider_id} → {self.employee.email}"


# ======================================================
# EMAIL VERIFICATION (per-tenant)
# ======================================================
class EmailVerification(models.Model):
    """
    Stores the PIN sent to a newly created employee for email
    verification. Deleted once the PIN is confirmed.
    Deleted once the PIN is confirmed.

    Only used for employees created by an admin (email+password path).
    Admin accounts are always verified before or during registration.
    """

    employee   = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name="email_verification",
    )
    pin        = models.CharField(max_length=128)
    attempts   = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.pk:
            self.expires_at = timezone.now() + timedelta(minutes=30)
        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"EmailVerification({self.employee.email})"
