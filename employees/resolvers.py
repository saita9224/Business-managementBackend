from sqlalchemy.orm import Session
from models import Role, Permission, RolePermission
from database import get_db


# ==========================================================
# QUERY RESOLVERS
# ==========================================================

def resolve_roles(root, info):
    db: Session = next(get_db())
    return db.query(Role).all()


def resolve_role(root, info, id: int):
    db: Session = next(get_db())
    return db.query(Role).filter(Role.id == id).first()


def resolve_permissions(root, info):
    db: Session = next(get_db())
    return db.query(Permission).all()


def resolve_permission(root, info, id: int):
    db: Session = next(get_db())
    return db.query(Permission).filter(Permission.id == id).first()


def resolve_role_permissions(root, info):
    db: Session = next(get_db())
    return db.query(RolePermission).all()


# ==========================================================
# MUTATION RESOLVERS — ROLES
# ==========================================================

def resolve_create_role(root, info, name: str, description: str = None):
    db: Session = next(get_db())

    new_role = Role(name=name, description=description)
    db.add(new_role)
    db.commit()
    db.refresh(new_role)
    return new_role


def resolve_update_role(root, info, id: int, name: str = None, description: str = None):
    db: Session = next(get_db())
    role = db.query(Role).filter(Role.id == id).first()

    if not role:
        raise Exception("Role not found")

    if name is not None:
        role.name = name
    if description is not None:
        role.description = description

    db.commit()
    db.refresh(role)
    return role


def resolve_delete_role(root, info, id: int):
    db: Session = next(get_db())
    role = db.query(Role).filter(Role.id == id).first()

    if not role:
        return False

    db.delete(role)
    db.commit()
    return True


# ==========================================================
# MUTATION RESOLVERS — PERMISSIONS
# ==========================================================

def resolve_create_permission(root, info, name: str, description: str = None):
    db: Session = next(get_db())

    new_perm = Permission(name=name, description=description)
    db.add(new_perm)
    db.commit()
    db.refresh(new_perm)
    return new_perm


def resolve_update_permission(root, info, id: int, name: str = None, description: str = None):
    db: Session = next(get_db())
    perm = db.query(Permission).filter(Permission.id == id).first()

    if not perm:
        raise Exception("Permission not found")

    if name is not None:
        perm.name = name
    if description is not None:
        perm.description = description

    db.commit()
    db.refresh(perm)
    return perm


def resolve_delete_permission(root, info, id: int):
    db: Session = next(get_db())
    perm = db.query(Permission).filter(Permission.id == id).first()

    if not perm:
        return False

    db.delete(perm)
    db.commit()
    return True


# ==========================================================
# MUTATION RESOLVERS — ROLE ↔ PERMISSION LINK
# ==========================================================

def resolve_assign_permission_to_role(root, info, role_id: int, permission_id: int):
    db: Session = next(get_db())

    role = db.query(Role).filter(Role.id == role_id).first()
    perm = db.query(Permission).filter(Permission.id == permission_id).first()

    if not role or not perm:
        raise Exception("Role or Permission not found")

    # Check if link already exists
    existing = (
        db.query(RolePermission)
        .filter(RolePermission.role_id == role_id,
                RolePermission.permission_id == permission_id)
        .first()
    )

    if existing:
        return existing

    link = RolePermission(role_id=role_id, permission_id=permission_id)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def resolve_remove_permission_from_role(root, info, role_id: int, permission_id: int):
    db: Session = next(get_db())

    link = (
        db.query(RolePermission)
        .filter(RolePermission.role_id == role_id,
                RolePermission.permission_id == permission_id)
        .first()
    )

    if not link:
        return False

    db.delete(link)
    db.commit()
    return True
