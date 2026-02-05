from django.contrib import admin
from .models import Employee, Role, Permission


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "is_active", "is_staff")
    search_fields = ("email", "name")
    filter_horizontal = ("roles",)


admin.site.register(Role)
admin.site.register(Permission)
