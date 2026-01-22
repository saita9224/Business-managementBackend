# employees/mutations.py

import typing
import strawberry
from strawberry.types import Info

from .decorators import permission_required
from .types import (
    EmployeeType,
    RoleType,
    PermissionType,
    RolePermissionType,
    EmployeeInput,
)
from . import services


@strawberry.type
class EmployeeMutation:

    # ---------- ROLE ----------

    @strawberry.mutation
    @permission_required("role.create")
    def create_role(
        self,
        info: Info,
        name: str,
        description: typing.Optional[str] = None,
    ) -> RoleType:
        role = services.create_role(name, description)
        return RoleType(id=role.id, name=role.name, description=role.description)

    @strawberry.mutation
    @permission_required("role.update")
    def update_role(
        self,
        info: Info,
        id: int,
        name: typing.Optional[str] = None,
        description: typing.Optional[str] = None,
    ) -> RoleType:
        role = services.update_role(id, name=name, description=description)
        return RoleType(id=role.id, name=role.name, description=role.description)

    @strawberry.mutation
    @permission_required("role.delete")
    def delete_role(self, info: Info, id: int) -> bool:
        return services.delete_role(id)

    # ---------- PERMISSION ----------

    @strawberry.mutation
    @permission_required("role.create")
    def create_permission(
        self,
        info: Info,
        code: str,
        description: typing.Optional[str] = None,
    ) -> PermissionType:
        perm = services.create_permission(code, description)
        return PermissionType(id=perm.id, name=perm.name, description=perm.description)

    @strawberry.mutation
    @permission_required("role.update")
    def update_permission(
        self,
        info: Info,
        id: int,
        name: typing.Optional[str] = None,
        description: typing.Optional[str] = None,
    ) -> PermissionType:
        perm = services.update_permission(id, name=name, description=description)
        return PermissionType(id=perm.id, name=perm.name, description=perm.description)

    @strawberry.mutation
    @permission_required("role.delete")
    def delete_permission(self, info: Info, id: int) -> bool:
        return services.delete_permission(id)

    # ---------- ROLE ↔ PERMISSION ----------

    @strawberry.mutation
    @permission_required("role.update")
    def assign_permission_to_role(
        self,
        info: Info,
        role_id: int,
        permission_id: int,
    ) -> RolePermissionType:
        link = services.assign_permission_to_role(role_id, permission_id)
        return RolePermissionType(
            id=link.id,
            role=RoleType(
                id=link.role.id,
                name=link.role.name,
                description=link.role.description,
            ),
            permission=PermissionType(
                id=link.permission.id,
                name=link.permission.name,
                description=link.permission.description,
            ),
        )

    @strawberry.mutation
    @permission_required("role.update")
    def remove_permission_from_role(
        self,
        info: Info,
        role_id: int,
        permission_id: int,
    ) -> bool:
        return services.remove_permission_from_role(role_id, permission_id)

    # ---------- EMPLOYEE ----------

    @strawberry.mutation
    @permission_required("employee.create")
    def create_employee(
        self,
        info: Info,
        data: EmployeeInput,
    ) -> EmployeeType:
        return services.create_employee(
            name=data.name,
            email=data.email,
            phone=data.phone,
            password=data.password,
            role_names=data.role_names,
        )

    @strawberry.mutation
    @permission_required("employee.update")
    def update_employee(
        self,
        info: Info,
        id: int,
        name: typing.Optional[str] = None,
        email: typing.Optional[str] = None,
        phone: typing.Optional[str] = None,
        password: typing.Optional[str] = None,
        role_names: typing.Optional[typing.List[str]] = None,
    ) -> EmployeeType:
        return services.update_employee(
            employee_id=id,
            name=name,
            email=email,
            phone=phone,
            password=password,
            role_names=role_names,
        )

    @strawberry.mutation
    @permission_required("employee.delete")
    def delete_employee(self, info: Info, id: int) -> bool:
        return services.delete_employee(id)
