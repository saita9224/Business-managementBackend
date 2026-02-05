# employees/models.py

from django.db import models
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
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True, db_index=True)
    phone = models.CharField(max_length=20, blank=True, null=True)

    roles = models.ManyToManyField(
        "Role",
        through="EmployeeRole",
        related_name="employees",
        blank=True,
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # REQUIRED for Django admin

    created_at = models.DateTimeField(auto_now_add=True)

    objects = EmployeeManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    def __str__(self):
        return self.name


# ======================================================
# ROLE MODEL
# ======================================================
class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

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
    code = models.CharField(max_length=150, unique=True)
    name = models.CharField(max_length=150, unique=True)
    description = models.CharField(max_length=250)

    def __str__(self):
        return self.name


# ======================================================
# ROLE → PERMISSION
# ======================================================
class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
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
    role = models.ForeignKey(Role, on_delete=models.CASCADE)

    class Meta:
        indexes = [
            models.Index(fields=["employee", "role"]),
        ]
        unique_together = ("employee", "role")

    def __str__(self):
        return f"{self.employee.email} → {self.role.name}"
