# employees/schema.py

import typing
import strawberry
from strawberry.types import Info

from .models import Employee, Role, Permission, RolePermission
from .decorators import permission_required


# ======================================================
# GRAPHQL TYPES
# ======================================================

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
    def permissions(self) -> typing.List["PermissionType"]:
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
        roles = self.roles.all()   # now safe because we return the Django model
        return [
            RoleType(id=r.id, name=r.name, description=r.description)
            for r in roles
        ]


@strawberry.type
class RolePermissionType:
    id: strawberry.ID
    role: RoleType
    permission: PermissionType


# ======================================================
# INPUT TYPES
# ======================================================

@strawberry.input
class EmployeeInput:
    name: str
    email: str
    phone: typing.Optional[str] = None
    password: str
    role_names: typing.List[str]


# ======================================================
# QUERY ROOT
# ======================================================

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
        if not r:
            return None
        return RoleType(id=r.id, name=r.name, description=r.description)

    @strawberry.field
    def permissions(self, info: Info) -> typing.List[PermissionType]:
        return [
            PermissionType(id=p.id, name=p.name, description=p.description)
            for p in Permission.objects.all()
        ]

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

    @strawberry.field
    def employees(self, info: Info) -> typing.List[EmployeeType]:
        return list(Employee.objects.all())   # safe: Strawberry wraps them


# ======================================================
# MUTATION ROOT
# ======================================================

@strawberry.type
class EmployeeMutation:

    # -----------------------------------------
    # ROLE CRUD
    # -----------------------------------------
    @strawberry.mutation
    @permission_required("role.create")
    def create_role(self, info: Info, name: str, description: typing.Optional[str] = None) -> RoleType:
        role = Role.objects.create(name=name, description=description)
        return RoleType(id=role.id, name=role.name, description=role.description)

    @strawberry.mutation
    @permission_required("role.update")
    def update_role(self, info: Info, id: int, name: typing.Optional[str] = None,
                    description: typing.Optional[str] = None) -> RoleType:

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

    # -----------------------------------------
    # PERMISSION CRUD
    # -----------------------------------------
    @strawberry.mutation
    @permission_required("role.create")
    def create_permission(self, info: Info, name: str,
                          description: typing.Optional[str] = None) -> PermissionType:

        perm, created = Permission.objects.get_or_create(
            name=name,
            defaults={"description": description or ""}
        )
        return PermissionType(id=perm.id, name=perm.name, description=perm.description)

    @strawberry.mutation
    @permission_required("role.update")
    def update_permission(self, info: Info, id: int, name: typing.Optional[str] = None,
                          description: typing.Optional[str] = None) -> PermissionType:

        perm = Permission.objects.filter(id=id).first()
        if not perm:
            raise Exception("Permission not found")

        if name:
            perm.name = name
        if description:
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

    # -----------------------------------------
    # LINK PERMISSION — ROLE
    # -----------------------------------------
    @strawberry.mutation
    @permission_required("role.update")
    def assign_permission_to_role(self, info: Info, role_id: int, permission_id: int) -> RolePermissionType:

        role = Role.objects.filter(id=role_id).first()
        perm = Permission.objects.filter(id=permission_id).first()

        if not role or not perm:
            raise Exception("Role or Permission not found")

        link, created = RolePermission.objects.get_or_create(role=role, permission=perm)

        return RolePermissionType(
            id=link.id,
            role=RoleType(id=role.id, name=role.name, description=role.description),
            permission=PermissionType(id=perm.id, name=perm.name, description=perm.description)
        )

    @strawberry.mutation
    @permission_required("role.update")
    def remove_permission_from_role(self, info: Info, role_id: int, permission_id: int) -> bool:
        link = RolePermission.objects.filter(role_id=role_id, permission_id=permission_id).first()
        if not link:
            return False
        link.delete()
        return True

    # -----------------------------------------
    # CREATE EMPLOYEE
    # -----------------------------------------
    @strawberry.mutation
    @permission_required("employee.create")
    def create_employee(self, info: Info, data: EmployeeInput) -> EmployeeType:

        if Employee.objects.filter(email=data.email).exists():
            raise Exception(f"An employee with email '{data.email}' already exists")

        role_objects = []
        for role_name in data.role_names:
            role_name = role_name.strip()
            role_obj, created = Role.objects.get_or_create(
                name=role_name,
                defaults={"description": f"Auto-created role: {role_name}"}
            )
            role_objects.append(role_obj)

        employee = Employee.objects.create(
            name=data.name,
            email=data.email,
            phone=data.phone or "",
            password="TEMP"
        )

        employee.set_password(data.password)
        employee.save()

        employee.roles.set(role_objects)

        return employee   # <-- FIXED

    # -----------------------------------------
    # UPDATE EMPLOYEE
    # -----------------------------------------
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

        employee = Employee.objects.filter(id=id).first()
        if not employee:
            raise Exception("Employee not found")

        if email and Employee.objects.exclude(id=id).filter(email=email).exists():
            raise Exception(f"Email '{email}' is already in use")

        if name:
            employee.name = name
        if email:
            employee.email = email
        if phone:
            employee.phone = phone

        if password:
            employee.set_password(password)

        employee.save()

        if role_names is not None:
            roles = []
            for r_name in role_names:
                r_obj, c = Role.objects.get_or_create(
                    name=r_name.strip(),
                    defaults={"description": f"Auto role: {r_name}"}
                )
                roles.append(r_obj)
            employee.roles.set(roles)

        return employee   # <-- FIXED

    # -----------------------------------------
    # DELETE EMPLOYEE
    # -----------------------------------------
    @strawberry.mutation
    @permission_required("employee.delete")
    def delete_employee(self, info: Info, id: int) -> bool:
        employee = Employee.objects.filter(id=id).first()
        if not employee:
            return False
        employee.delete()
        return True


# ======================================================
# FINAL EXPORTS
# ======================================================

__all__ = ["EmployeeQuery", "EmployeeMutation"]
