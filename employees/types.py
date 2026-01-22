# employees/types.py

import typing
import strawberry

from .models import Permission


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
class EmployeeType:
    id: strawberry.ID
    name: str
    email: str
    phone: typing.Optional[str]
    is_active: bool

    @strawberry.field(name="roles")
    def resolve_roles(self) -> typing.List[RoleType]:
        return [
            RoleType(id=r.id, name=r.name, description=r.description)
            for r in self.roles.all()
        ]


@strawberry.type
class RolePermissionType:
    id: strawberry.ID
    role: RoleType
    permission: PermissionType


# ----------------------
# INPUT TYPES
# ----------------------

@strawberry.input
class EmployeeInput:
    name: str
    email: str
    phone: typing.Optional[str] = None
    password: str
    role_names: typing.List[str]
