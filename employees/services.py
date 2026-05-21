# employees/services.py

import logging
from typing import List, Optional

from django.db import transaction
from django.core.exceptions import ValidationError

from .models import (
    Employee,
    Role,
    Permission,
    RolePermission,
    EmployeeRole,
    EmailVerification,
)

logger = logging.getLogger(__name__)


# ======================================================
# ROLE SERVICES
# ======================================================

def create_role(name: str, description: Optional[str] = None) -> Role:
    return Role.objects.create(name=name, description=description)


def update_role(
    role_id: int,
    *,
    name:        Optional[str] = None,
    description: Optional[str] = None,
) -> Role:
    role = Role.objects.filter(id=role_id).first()
    if not role:
        raise ValidationError("Role not found")
    if name        is not None: role.name        = name
    if description is not None: role.description = description
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

def create_permission(
    code:        str,
    description: Optional[str] = None,
) -> Permission:
    perm, _ = Permission.objects.get_or_create(
        code=code,
        defaults={
            "name":        code,
            "description": description or code,
        },
    )
    return perm


def update_permission(
    permission_id: int,
    *,
    name:        Optional[str] = None,
    description: Optional[str] = None,
) -> Permission:
    perm = Permission.objects.filter(id=permission_id).first()
    if not perm:
        raise ValidationError("Permission not found")
    if name        is not None: perm.name        = name
    if description is not None: perm.description = description
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

def assign_permission_to_role(
    role_id:       int,
    permission_id: int,
) -> RolePermission:
    role = Role.objects.filter(id=role_id).first()
    perm = Permission.objects.filter(id=permission_id).first()
    if not role or not perm:
        raise ValidationError("Role or Permission not found")
    link, _ = RolePermission.objects.get_or_create(role=role, permission=perm)
    return link


def remove_permission_from_role(
    role_id:       int,
    permission_id: int,
) -> bool:
    link = RolePermission.objects.filter(
        role_id=role_id,
        permission_id=permission_id,
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
    name:       str,
    email:      str,
    phone:      Optional[str],
    password:   str,
    role_names: List[str],
) -> tuple[Employee, str]:
    """
    Create a basic employee with named roles.

    Returns (employee, plain_password) so the caller can
    include the plain password in the welcome email before
    it is hashed and lost.
    """
    if Employee.objects.filter(email=email).exists():
        raise ValidationError(
            f"An employee with email '{email}' already exists"
        )

    roles: list[Role] = []
    for role_name in role_names:
        role_name = role_name.strip()
        role, _ = Role.objects.get_or_create(
            name=role_name,
            defaults={"description": f"Auto-created role: {role_name}"},
        )
        roles.append(role)

    employee = Employee(
        name=name,
        email=email,
        phone=phone or "",
        is_email_verified=False,  # employee must verify on first login
    )
    employee.set_password(password)
    employee.save()
    employee.roles.set(roles)

    return employee, password


@transaction.atomic
def update_employee(
    *,
    employee_id: int,
    name:        Optional[str] = None,
    email:       Optional[str] = None,
    phone:       Optional[str] = None,
    password:    Optional[str] = None,
    role_names:  Optional[List[str]] = None,
) -> Employee:

    employee = Employee.objects.filter(id=employee_id).first()
    if not employee:
        raise ValidationError("Employee not found")

    if email and Employee.objects.exclude(id=employee_id).filter(email=email).exists():
        raise ValidationError(f"Email '{email}' is already in use")

    if name  is not None: employee.name  = name
    if email is not None: employee.email = email
    if phone is not None: employee.phone = phone

    if password:
        employee.set_password(password)

    employee.save()

    if role_names is not None:
        roles: list[Role] = []
        for role_name in role_names:
            role_name = role_name.strip()
            role, _ = Role.objects.get_or_create(
                name=role_name,
                defaults={"description": f"Auto-created role: {role_name}"},
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


# ======================================================
# ONBOARD EMPLOYEE — ATOMIC
#
# Creates Employee + personal Role + RolePermissions in a
# single transaction. Sends verification email after commit.
# ======================================================

@transaction.atomic
def onboard_employee(
    *,
    name:             str,
    email:            str,
    phone:            Optional[str],
    password:         str,
    permission_codes: List[str],
) -> tuple[Employee, str]:
    """
    Create an employee and assign granular permissions atomically.

    Returns (employee, plain_password) so the caller can pass the
    plain password to the welcome email before it is hashed.
    """

    if Employee.objects.filter(email=email).exists():
        raise ValidationError(
            f"An employee with email '{email}' already exists."
        )

    if not permission_codes:
        raise ValidationError(
            "At least one permission must be selected."
        )

    # 1. Create employee — unverified until they confirm PIN
    employee = Employee(
        name=name,
        email=email,
        phone=phone or "",
        is_email_verified=False,
    )
    employee.set_password(password)
    employee.save()

    # 2. Create personal role
    role_name = f"{name.strip().replace(' ', '_')}_{employee.id}"
    role = Role.objects.create(
        name=role_name,
        description=f"Personal role for {name}",
    )

    # 3. Fetch permissions in one query
    permissions = Permission.objects.filter(code__in=permission_codes)

    unrecognised = set(permission_codes) - {p.code for p in permissions}
    if unrecognised:
        raise ValidationError(
            f"Unknown permission codes: {', '.join(sorted(unrecognised))}"
        )

    # 4. Bulk create RolePermission records
    RolePermission.objects.bulk_create([
        RolePermission(role=role, permission=perm)
        for perm in permissions
    ])

    # 5. Assign role to employee
    EmployeeRole.objects.create(employee=employee, role=role)

    return employee, password


# ======================================================
# EMAIL VERIFICATION SERVICES
# ======================================================

def create_employee_verification_pin(employee: Employee) -> str:
    """
    Generate a 6-digit PIN and store it in EmailVerification
    for the given employee. Replaces any existing PIN (resend).

    Returns the plain PIN so the caller can email it.
    Sync — call via sync_to_async from async mutations.
    """
    from authentication.models import generate_pin

    pin = generate_pin()

    # Replace any existing verification record (covers resend case)
    EmailVerification.objects.filter(employee=employee).delete()
    EmailVerification.objects.create(employee=employee, pin=pin)

    logger.info("Created email verification PIN for %s", employee.email)
    return pin


def verify_employee_email_pin(employee: Employee, pin: str) -> None:
    """
    Verify an employee's email PIN.

    On success: marks employee as verified, deletes the record.
    On failure: raises ValueError with a user-facing message.
    Sync — call via sync_to_async from async mutations.
    """
    try:
        verification = EmailVerification.objects.get(employee=employee)
    except EmailVerification.DoesNotExist:
        raise ValueError(
            "No verification PIN found for your account. "
            "Ask your admin to resend the verification email."
        )

    if verification.pin != pin:
        raise ValueError(
            "Incorrect PIN. Please check your email and try again."
        )

    employee.is_email_verified = True
    employee.save(update_fields=["is_email_verified"])
    verification.delete()

    logger.info("Email verified for %s", employee.email)