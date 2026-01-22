# employees/queries.py

import typing
import strawberry
from strawberry.types import Info

from .models import Employee, Role, Permission, RolePermission
from .types import (
    EmployeeType,
    RoleType,
    PermissionType,
    RolePermissionType,
)


@strawberry.type
class EmployeeQuery:

    @strawberry.field
    def roles(self, info: Info) -> typing.List[RoleType]:
        return [
            RoleType(id=r.id, name=r.name, description=r.description)
            for r in Role.objects.all()
        ]

    @strawberry.field
    def role(self, info: Info, id: int) -> typing.Optional[RoleType]:
        r = Role.objects.filter(id=id).first()
        return RoleType(id=r.id, name=r.name, description=r.description) if r else None

    @strawberry.field
    def permissions(self, info: Info) -> typing.List[PermissionType]:
        return [
            PermissionType(id=p.id, name=p.name, description=p.description)
            for p in Permission.objects.all()
        ]

    @strawberry.field
    def permission(self, info: Info, id: int) -> typing.Optional[PermissionType]:
        p = Permission.objects.filter(id=id).first()
        return PermissionType(id=p.id, name=p.name, description=p.description) if p else None

    @strawberry.field
    def role_permissions(self, info: Info) -> typing.List[RolePermissionType]:
        links = RolePermission.objects.select_related("role", "permission")
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

    @strawberry.field
    def employees(self, info: Info) -> typing.List[EmployeeType]:
        return list(Employee.objects.prefetch_related("roles").all())
