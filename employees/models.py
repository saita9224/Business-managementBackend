from django.db import models
from django.contrib.auth.hashers import make_password, check_password


# ----------------------------
# Employee Model
# ----------------------------
class Employee(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)

    role = models.ForeignKey(
        "Role",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees"
    )

    is_active = models.BooleanField(default=True)

    password = models.CharField(max_length=256)

    created_at = models.DateTimeField(auto_now_add=True)

    def set_password(self, raw_password):
        self.password = make_password(raw_password)
        self.save()

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.name} ({self.role.name if self.role else 'No Role'})"


# ----------------------------
# Role Model
# ----------------------------
class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# ----------------------------
# Permission Model
# ----------------------------
class Permission(models.Model):
    code = models.CharField(max_length=150, unique=True)
    description = models.CharField(max_length=250)

    def __str__(self):
        return self.code


# ----------------------------
# RolePermission (Many-to-Many)
# ----------------------------
class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('role', 'permission')

    def __str__(self):
        return f"{self.role.name} → {self.permission.code}"
