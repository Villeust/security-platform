from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models.admin import Permission, Role, RolePermission, User
from app.services.admin_service import SYSTEM_ROLES, get_or_404
from app.services.audit_service import write_audit

PERMISSIONS: dict[str, tuple[str, str | None]] = {
    "admin.dashboard.view": ("View admin dashboard", None),
    "admin.contractors.view": ("View contractors", None),
    "admin.contractors.manage": ("Manage contractors", None),
    "admin.users.view": ("View users", None),
    "admin.users.manage": ("Manage users", None),
    "admin.roles.view": ("View roles", None),
    "admin.roles.manage": ("Manage roles", None),
    "admin.audit.view": ("View audit", None),
    "admin.system_status.view": ("View system status", None),
    "requests.view": ("View requests", None),
    "requests.create": ("Create requests", None),
    "requests.update": ("Update requests", None),
    "requests.publish": ("Publish requests", None),
    "requests.change_status": ("Change request status", None),
    "requests.close": ("Close requests", None),
    "requests.comments.internal": ("Use internal request comments", None),
    "requests.attachments.internal": ("Use internal request attachments", None),
    "contractor.requests.view": ("View contractor requests", None),
    "contractor.requests.accept": ("Accept contractor assignments", None),
    "contractor.requests.update_status": ("Update contractor assignment status", None),
    "contractor.comments.create": ("Create contractor comments", None),
    "contractor.attachments.upload": ("Upload contractor attachments", None),
    "reference_data.view": ("View reference data", None),
    "reference_data.manage": ("Manage reference data", None),
}

ALL_PERMISSION_CODES = set(PERMISSIONS)

SECURITY_ADMIN_PERMISSIONS = ALL_PERMISSION_CODES - {
    "contractor.requests.view",
    "contractor.requests.accept",
    "contractor.requests.update_status",
    "contractor.comments.create",
    "contractor.attachments.upload",
}

SECURITY_OPERATOR_PERMISSIONS = {
    "requests.view",
    "requests.create",
    "requests.update",
    "requests.publish",
    "requests.change_status",
    "requests.comments.internal",
    "requests.attachments.internal",
    "reference_data.view",
}

CONTRACTOR_PERMISSIONS = {
    "contractor.requests.view",
    "contractor.requests.accept",
    "contractor.requests.update_status",
    "contractor.comments.create",
    "contractor.attachments.upload",
}

VIEWER_PERMISSIONS = {
    "admin.dashboard.view",
    "requests.view",
    "reference_data.view",
}

ROLE_PERMISSION_CODES: dict[str, set[str]] = {
    "PLATFORM_ADMIN": ALL_PERMISSION_CODES,
    "SECURITY_ADMIN": SECURITY_ADMIN_PERMISSIONS,
    "SECURITY_OPERATOR": SECURITY_OPERATOR_PERMISSIONS,
    "CONTRACTOR_MANAGER": CONTRACTOR_PERMISSIONS,
    "CONTRACTOR_USER": CONTRACTOR_PERMISSIONS,
    "VIEWER": VIEWER_PERMISSIONS,
}


def split_permission_code(code: str) -> tuple[str, str]:
    resource, _, action = code.rpartition(".")
    return resource, action


def seed_rbac(db: Session) -> None:
    roles_by_code = {role.code: role for role in db.scalars(select(Role)).all()}
    for code, name in SYSTEM_ROLES.items():
        role = roles_by_code.get(code)
        if role is None:
            role = Role(code=code, name=name, description=f"System role: {name}", is_system=True, is_active=True)
            db.add(role)
            db.flush()
            roles_by_code[code] = role

    permissions_by_code = {permission.code: permission for permission in db.scalars(select(Permission)).all()}
    for code, (name, description) in PERMISSIONS.items():
        resource, action = split_permission_code(code)
        permission = permissions_by_code.get(code)
        if permission is None:
            permission = Permission(code=code, name=name, description=description, resource=resource, action=action, is_system=True, is_active=True)
            db.add(permission)
            db.flush()
            permissions_by_code[code] = permission
        else:
            permission.name = name
            permission.description = description
            permission.resource = resource
            permission.action = action
            permission.is_system = True

    existing = {
        (item.role_id, item.permission_id)
        for item in db.scalars(select(RolePermission)).all()
    }
    for role_code, permission_codes in ROLE_PERMISSION_CODES.items():
        role = roles_by_code[role_code]
        for permission_code in permission_codes:
            permission = permissions_by_code[permission_code]
            key = (role.id, permission.id)
            if key not in existing:
                db.add(RolePermission(role_id=role.id, permission_id=permission.id))
                existing.add(key)
    db.commit()


def permission_codes_for_user(user: User) -> set[str]:
    codes: set[str] = set()
    for user_role in user.roles:
        role = user_role.role
        if role is None or not role.is_active:
            continue
        for role_permission in role.permissions:
            permission = role_permission.permission
            if permission is not None and permission.is_active:
                codes.add(permission.code)
    return codes


def list_permissions(db: Session) -> list[Permission]:
    seed_rbac(db)
    return list(db.scalars(select(Permission).order_by(Permission.resource, Permission.action)).all())


def get_role_permissions(db: Session, role_id: UUID) -> list[Permission]:
    seed_rbac(db)
    role = db.scalar(select(Role).where(Role.id == role_id).options(selectinload(Role.permissions).selectinload(RolePermission.permission)))
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return [item.permission for item in role.permissions if item.permission is not None]


def set_role_permissions(db: Session, role_id: UUID, permission_ids: list[UUID], actor_id: UUID | None = None) -> list[Permission]:
    seed_rbac(db)
    role = get_or_404(db, Role, role_id)
    permissions = list(db.scalars(select(Permission).where(Permission.id.in_(permission_ids))).all()) if permission_ids else []
    if len(permissions) != len(set(permission_ids)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more permissions not found")
    if any(not permission.is_active for permission in permissions):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Inactive permission cannot be assigned")
    if role.code == "PLATFORM_ADMIN":
        requested_codes = {permission.code for permission in permissions}
        if not ALL_PERMISSION_CODES.issubset(requested_codes):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PLATFORM_ADMIN must keep all system permissions")

    old = {"permission_codes": sorted(permission.code for permission in get_role_permissions(db, role_id))}
    db.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
    db.flush()
    db.add_all(RolePermission(role_id=role.id, permission_id=permission.id) for permission in permissions)
    write_audit(
        db,
        "ROLE_PERMISSIONS_CHANGED",
        "Role",
        role.id,
        old_data=old,
        new_data={"permission_codes": sorted(permission.code for permission in permissions)},
        actor_id=actor_id,
    )
    db.commit()
    return get_role_permissions(db, role_id)
