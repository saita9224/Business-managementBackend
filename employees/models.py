from django.db import models
from django.contrib.auth.hashers import make_password, check_password


# ======================================================
# EMPLOYEE MODEL
# ======================================================
class Employee(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)

    # Proper Many-to-Many through EmployeeRole
    roles = models.ManyToManyField(
        "Role",
        through="EmployeeRole",
        related_name="employees"
    )

    is_active = models.BooleanField(default=True)

    password = models.CharField(max_length=256)
    created_at = models.DateTimeField(auto_now_add=True)

    # Password helpers
    def set_password(self, raw_password):
        self.password = make_password(raw_password)
        self.save()

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.name}"


# ======================================================
# ROLE MODEL
# ======================================================
class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Many-to-Many: Role → Permission through RolePermission
    permissions = models.ManyToManyField(
        "Permission",
        through="RolePermission",
        related_name="roles"
    )

    def __str__(self):
        return self.name


# ======================================================
# PERMISSION MODEL
# ======================================================
class Permission(models.Model):
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
        return f"{self.role.name} → {self.permission.name}"


# ======================================================
# EMPLOYEE → ROLE (Many-to-Many)
# ======================================================
class EmployeeRole(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("employee", "role")

    def __str__(self):
        return f"{self.employee.name} → {self.role.name}"
