# employees/services.py

from typing import List, Optional

from django.db import transaction
from django.core.exceptions import ValidationError

from .models import Employee, Role, Permission, RolePermission


# ======================================================
# ROLE SERVICES
# ======================================================

def create_role(name: str, description: Optional[str] = None) -> Role:
    return Role.objects.create(name=name, description=description)


def update_role(role_id: int, *, name: Optional[str] = None, description: Optional[str] = None) -> Role:
    role = Role.objects.filter(id=role_id).first()
    if not role:
        raise ValidationError("Role not found")

    if name is not None:
        role.name = name
    if description is not None:
        role.description = description

    role.save()
    return role


def delete_role(role_id: int) -> bool:
    role = Role.objects.filter(id=role_id).first()
    if not role:
        return False
    role.delete()
    return True


# ======================================================
# PERMISSION SERVICES
# ======================================================

def create_permission(code: str, description: Optional[str] = None) -> Permission:
    perm, _ = Permission.objects.get_or_create(
        code=code,
        defaults={
            "name": code,
            "description": description or code,
        },
    )
    return perm


def update_permission(permission_id: int, *, name: Optional[str] = None,
                      description: Optional[str] = None) -> Permission:
    perm = Permission.objects.filter(id=permission_id).first()
    if not perm:
        raise ValidationError("Permission not found")

    if name is not None:
        perm.name = name
    if description is not None:
        perm.description = description

    perm.save()
    return perm


def delete_permission(permission_id: int) -> bool:
    perm = Permission.objects.filter(id=permission_id).first()
    if not perm:
        return False
    perm.delete()
    return True


# ======================================================
# ROLE ↔ PERMISSION SERVICES
# ======================================================

def assign_permission_to_role(role_id: int, permission_id: int) -> RolePermission:
    role = Role.objects.filter(id=role_id).first()
    perm = Permission.objects.filter(id=permission_id).first()

    if not role or not perm:
        raise ValidationError("Role or Permission not found")

    link, _ = RolePermission.objects.get_or_create(role=role, permission=perm)
    return link


def remove_permission_from_role(role_id: int, permission_id: int) -> bool:
    link = RolePermission.objects.filter(
        role_id=role_id,
        permission_id=permission_id
    ).first()

    if not link:
        return False

    link.delete()
    return True


# ======================================================
# EMPLOYEE SERVICES
# ======================================================

@transaction.atomic
def create_employee(
    *,
    name: str,
    email: str,
    phone: Optional[str],
    password: str,
    role_names: List[str],
) -> Employee:

    if Employee.objects.filter(email=email).exists():
        raise ValidationError(f"An employee with email '{email}' already exists")

    roles: list[Role] = []
    for role_name in role_names:
        role_name = role_name.strip()
        role, _ = Role.objects.get_or_create(
            name=role_name,
            defaults={"description": f"Auto-created role: {role_name}"}
        )
        roles.append(role)

    employee = Employee.objects.create(
        name=name,
        email=email,
        phone=phone or "",
    )

    employee.set_password(password)
    employee.save()
    employee.roles.set(roles)

    return employee


@transaction.atomic
def update_employee(
    *,
    employee_id: int,
    name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    password: Optional[str] = None,
    role_names: Optional[List[str]] = None,
) -> Employee:

    employee = Employee.objects.filter(id=employee_id).first()
    if not employee:
        raise ValidationError("Employee not found")

    if email and Employee.objects.exclude(id=employee_id).filter(email=email).exists():
        raise ValidationError(f"Email '{email}' is already in use")

    if name is not None:
        employee.name = name
    if email is not None:
        employee.email = email
    if phone is not None:
        employee.phone = phone

    if password:
        employee.set_password(password)

    employee.save()

    if role_names is not None:
        roles: list[Role] = []
        for role_name in role_names:
            role_name = role_name.strip()
            role, _ = Role.objects.get_or_create(
                name=role_name,
                defaults={"description": f"Auto-created role: {role_name}"}
            )
            roles.append(role)
        employee.roles.set(roles)

    return employee


def delete_employee(employee_id: int) -> bool:
    employee = Employee.objects.filter(id=employee_id).first()
    if not employee:
        return False
    employee.delete()
    return True
