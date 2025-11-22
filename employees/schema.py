# employees/schema.py

import typing
import strawberry
from strawberry.types import Info

from .models import Role, Permission, RolePermission
from .helpers import require_permission
from .decorators import permission_required


# -----------------------
# GraphQL Types
# -----------------------

@strawberry.type
class PermissionType:
    id: strawberry.ID
    name: str
    description: typing.Optional[str]


@strawberry.type
class RoleType:
    id: strawberry.ID
    name: str
    description: typing.Optional[str]

    @strawberry.field
    def permissions(self) -> typing.List[PermissionType]:
        perms = Permission.objects.filter(rolepermission__role_id=self.id)
        return [
            PermissionType(id=p.id, name=p.name, description=p.description)
            for p in perms
        ]


@strawberry.type
class RolePermissionType:
    id: strawberry.ID
    role: RoleType
    permission: PermissionType


# -----------------------
# Queries
# -----------------------

@strawberry.type
class EmployeeQuery:
    @strawberry.field
    def roles(self, info: Info) -> typing.List[RoleType]:
        qs = Role.objects.all()
        return [RoleType(id=r.id, name=r.name, description=r.description) for r in qs]

    @strawberry.field
    def role(self, info: Info, id: int) -> typing.Optional[RoleType]:
        r = Role.objects.filter(id=id).first()
        if not r:
            return None
        return RoleType(id=r.id, name=r.name, description=r.description)

    @strawberry.field
    def permissions(self, info: Info) -> typing.List[PermissionType]:
        qs = Permission.objects.all()
        return [PermissionType(id=p.id, name=p.name, description=p.description) for p in qs]

    @strawberry.field
    def permission(self, info: Info, id: int) -> typing.Optional[PermissionType]:
        p = Permission.objects.filter(id=id).first()
        if not p:
            return None
        return PermissionType(id=p.id, name=p.name, description=p.description)

    @strawberry.field
    def role_permissions(self, info: Info) -> typing.List[RolePermissionType]:
        links = RolePermission.objects.select_related("role", "permission").all()
        result = []
        for l in links:
            role_obj = RoleType(id=l.role.id, name=l.role.name, description=l.role.description)
            perm_obj = PermissionType(id=l.permission.id, name=l.permission.name, description=l.permission.description)
            result.append(RolePermissionType(id=l.id, role=role_obj, permission=perm_obj))
        return result


# -----------------------
# Mutations
# -----------------------

@strawberry.type
class EmployeeMutation:
    @strawberry.mutation
    @permission_required("role.create")
    def create_role(self, info: Info, name: str, description: typing.Optional[str] = None) -> RoleType:
        role = Role.objects.create(name=name, description=description)
        return RoleType(id=role.id, name=role.name, description=role.description)

    @strawberry.mutation
    @permission_required("role.update")
    def update_role(self, info: Info, id: int, name: typing.Optional[str] = None, description: typing.Optional[str] = None) -> RoleType:
        role = Role.objects.filter(id=id).first()
        if not role:
            raise Exception("Role not found")
        if name is not None:
            role.name = name
        if description is not None:
            role.description = description
        role.save()
        return RoleType(id=role.id, name=role.name, description=role.description)

    @strawberry.mutation
    @permission_required("role.delete")
    def delete_role(self, info: Info, id: int) -> bool:
        role = Role.objects.filter(id=id).first()
        if not role:
            return False
        role.delete()
        return True

    @strawberry.mutation
    @permission_required("role.create")
    def create_permission(self, info: Info, name: str, description: typing.Optional[str] = None) -> PermissionType:
        perm, created = Permission.objects.get_or_create(name=name, defaults={"description": description or ""})
        return PermissionType(id=perm.id, name=perm.name, description=perm.description)

    @strawberry.mutation
    @permission_required("role.update")
    def update_permission(self, info: Info, id: int, name: typing.Optional[str] = None, description: typing.Optional[str] = None) -> PermissionType:
        perm = Permission.objects.filter(id=id).first()
        if not perm:
            raise Exception("Permission not found")
        if name is not None:
            perm.name = name
        if description is not None:
            perm.description = description
        perm.save()
        return PermissionType(id=perm.id, name=perm.name, description=perm.description)

    @strawberry.mutation
    @permission_required("role.delete")
    def delete_permission(self, info: Info, id: int) -> bool:
        perm = Permission.objects.filter(id=id).first()
        if not perm:
            return False
        perm.delete()
        return True

    @strawberry.mutation
    @permission_required("role.update")
    def assign_permission_to_role(self, info: Info, role_id: int, permission_id: int) -> RolePermissionType:
        role = Role.objects.filter(id=role_id).first()
        perm = Permission.objects.filter(id=permission_id).first()
        if not role or not perm:
            raise Exception("Role or Permission not found")

        link, created = RolePermission.objects.get_or_create(role=role, permission=perm)
        role_obj = RoleType(id=role.id, name=role.name, description=role.description)
        perm_obj = PermissionType(id=perm.id, name=perm.name, description=perm.description)

        return RolePermissionType(id=link.id, role=role_obj, permission=perm_obj)

    @strawberry.mutation
    @permission_required("role.update")
    def remove_permission_from_role(self, info: Info, role_id: int, permission_id: int) -> bool:
        link = RolePermission.objects.filter(role_id=role_id, permission_id=permission_id).first()
        if not link:
            return False
        link.delete()
        return True


__all__ = ["EmployeeQuery", "EmployeeMutation"]
