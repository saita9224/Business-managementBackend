# employees/queries.py

import typing
import importlib
import strawberry
from strawberry.types import Info
from django.apps import apps
from asgiref.sync import sync_to_async

from .models import Employee, Role, Permission, RolePermission
from .types import (
    EmployeeType,
    RoleType,
    PermissionType,
    RolePermissionType,
)
from .decorators import permission_required


# ======================================================
# ENRICHED PERMISSION TYPES
# ======================================================

@strawberry.type
class RichPermissionType:
    code:         str
    display_name: str
    description:  str


@strawberry.type
class PermissionGroupType:
    app:         str
    label:       str
    permissions: typing.List[RichPermissionType]


APP_LABELS = {
    "pos":       "Point of Sale",
    "inventory": "Inventory",
    "expenses":  "Expenses",
    "hr":        "Human Resources",
    "employee":  "Employee Management",
    "role":      "Roles & Permissions",
}


def _load_all_permission_meta() -> dict[str, tuple[str, str]]:
    meta: dict[str, tuple[str, str]] = {}
    for app_config in apps.get_app_configs():
        module_name = f"{app_config.name}.permissions"
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, "PERMISSION_META"):
                meta.update(module.PERMISSION_META)
        except ModuleNotFoundError:
            continue
    return meta


# ======================================================
# EMPLOYEE QUERIES
# ======================================================

@strawberry.type
class EmployeeQuery:

    # ── ROLES ──────────────────────────────────────────

    @strawberry.field
    @permission_required("employee.view")
    async def roles(self, info: Info) -> typing.List[RoleType]:
        roles = await sync_to_async(list)(Role.objects.all())
        return [
            RoleType(id=r.id, name=r.name, description=r.description)
            for r in roles
        ]

    @strawberry.field
    @permission_required("employee.view")
    async def role(
        self, info: Info, id: int
    ) -> typing.Optional[RoleType]:
        r = await sync_to_async(Role.objects.filter(id=id).first)()
        return (
            RoleType(id=r.id, name=r.name, description=r.description)
            if r else None
        )

    # ── PERMISSIONS ────────────────────────────────────

    @strawberry.field
    @permission_required("employee.view")
    async def permissions(self, info: Info) -> typing.List[PermissionType]:
        perms = await sync_to_async(list)(Permission.objects.all())
        return [
            PermissionType(id=p.id, name=p.name, description=p.description)
            for p in perms
        ]

    @strawberry.field
    @permission_required("employee.view")
    async def permission(
        self, info: Info, id: int
    ) -> typing.Optional[PermissionType]:
        p = await sync_to_async(Permission.objects.filter(id=id).first)()
        return (
            PermissionType(id=p.id, name=p.name, description=p.description)
            if p else None
        )

    # ── GROUPED PERMISSIONS ────────────────────────────

    @strawberry.field
    @permission_required("employee.view")
    async def grouped_permissions(
        self, info: Info
    ) -> typing.List[PermissionGroupType]:
        meta = _load_all_permission_meta()

        all_permissions = await sync_to_async(list)(
            Permission.objects.all().order_by("code")
        )

        groups: dict[str, list[RichPermissionType]] = {}
        for perm in all_permissions:
            prefix = perm.code.split(".")[0]
            display_name, description = meta.get(
                perm.code,
                (perm.code, "No description available"),
            )
            groups.setdefault(prefix, []).append(
                RichPermissionType(
                    code=perm.code,
                    display_name=display_name,
                    description=description,
                )
            )

        result: list[PermissionGroupType] = []
        for prefix, label in APP_LABELS.items():
            if prefix in groups:
                result.append(
                    PermissionGroupType(
                        app=prefix,
                        label=label,
                        permissions=groups[prefix],
                    )
                )

        for prefix, perms in groups.items():
            if prefix not in APP_LABELS:
                result.append(
                    PermissionGroupType(
                        app=prefix,
                        label=prefix.replace("_", " ").title(),
                        permissions=perms,
                    )
                )

        return result

    # ── ROLE ↔ PERMISSION ──────────────────────────────

    @strawberry.field
    @permission_required("employee.view")
    async def role_permissions(
        self, info: Info
    ) -> typing.List[RolePermissionType]:
        links = await sync_to_async(list)(
            RolePermission.objects.select_related("role", "permission")
        )
        return [
            RolePermissionType(
                id=l.id,
                role=RoleType(
                    id=l.role.id,
                    name=l.role.name,
                    description=l.role.description,
                ),
                permission=PermissionType(
                    id=l.permission.id,
                    name=l.permission.name,
                    description=l.permission.description,
                ),
            )
            for l in links
        ]

    # ── EMPLOYEES ──────────────────────────────────────

    @strawberry.field
    @permission_required("employee.view")
    async def employees(self, info: Info) -> typing.List[EmployeeType]:
        return await sync_to_async(list)(
            Employee.objects.prefetch_related("roles").all()
        )