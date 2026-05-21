# authentication/admin.py

from django.contrib import admin
from employees.models import Employee, Role, Permission, EmployeeRole, RolePermission


# ======================================================
# INLINES
# ======================================================

class EmployeeRoleInline(admin.TabularInline):
    """
    Manages the Employee → Role relationship via the EmployeeRole
    through model. Required because filter_horizontal cannot be used
    on ManyToManyFields that specify an explicit through= model.
    """
    model = EmployeeRole
    extra = 1
    autocomplete_fields = ["role"]


class RolePermissionInline(admin.TabularInline):
    """
    Manages the Role → Permission relationship via RolePermission.
    Same reason — through model blocks filter_horizontal on Role.
    """
    model = RolePermission
    extra = 1
    autocomplete_fields = ["permission"]


# ======================================================
# EMPLOYEE ADMIN
# ======================================================

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    inlines = [EmployeeRoleInline]

    list_display   = ("email", "name", "is_active", "is_staff")
    search_fields  = ("email", "name")
    list_filter    = ("is_active", "is_staff")

    # roles is intentionally removed from filter_horizontal —
    # it uses a through model (EmployeeRole) so it must be
    # managed via the EmployeeRoleInline above.
    filter_horizontal = ()

    fieldsets = (
        (None, {
            "fields": ("name", "email", "phone", "password")
        }),
        ("Status", {
            "fields": ("is_active", "is_staff", "is_superuser")
        }),
        ("Django permissions", {
            "fields": ("groups", "user_permissions"),
            "classes": ("collapse",),
        }),
    )


# ======================================================
# ROLE ADMIN
# ======================================================

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    inlines = [RolePermissionInline]

    list_display  = ("name", "created_at")
    search_fields = ("name",)   # required for autocomplete_fields on EmployeeRoleInline


# ======================================================
# PERMISSION ADMIN
# ======================================================

@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display  = ("code", "name", "description")
    search_fields = ("code", "name")   # required for autocomplete_fields on RolePermissionInline