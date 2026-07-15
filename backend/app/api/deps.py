from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.session import get_db
from app.models.admin import AuthSource, ContractorMembership, Role, RolePermission, User, UserRole, UserType
from app.services.audit_service import write_audit
from app.services.rbac_service import permission_codes_for_user, seed_rbac


@dataclass(frozen=True)
class ContractorAuthContext:
    contractor_ids: set[UUID]
    actor_id: UUID | None
    user: User | None = None
    legacy_contractor_id: UUID | None = None


def dev_auth_enabled() -> bool:
    return settings.environment.lower() not in {"production", "prod"} and settings.allow_dev_auth_headers


def load_user(db: Session, user_id: UUID) -> User | None:
    return db.scalar(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.roles).selectinload(UserRole.role).selectinload(Role.permissions).selectinload(RolePermission.permission),
            selectinload(User.contractor_memberships).selectinload(ContractorMembership.contractor),
        )
    )


def get_current_user_stub(
    x_user_id: UUID | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    # TODO: Replace development headers with real authentication context.
    if not dev_auth_enabled():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required")
    seed_rbac(db)
    user: User | None = load_user(db, x_user_id) if x_user_id is not None else None
    if user is None and x_user_role:
        role = db.scalar(select(Role).where(Role.code == x_user_role))
        if role is not None:
            user = db.scalar(
                select(User)
                .join(UserRole)
                .where(UserRole.role_id == role.id, User.is_active.is_(True))
                .options(
                    selectinload(User.roles).selectinload(UserRole.role).selectinload(Role.permissions).selectinload(RolePermission.permission),
                    selectinload(User.contractor_memberships).selectinload(ContractorMembership.contractor),
                )
            )
            if user is None:
                user = User(
                    username=f"dev.{role.code.lower()}",
                    email=None,
                    display_name=role.name,
                    user_type=UserType.CONTRACTOR if role.code.startswith("CONTRACTOR_") else UserType.INTERNAL,
                    auth_source=AuthSource.LOCAL,
                    is_active=True,
                    is_locked=False,
                )
                db.add(user)
                db.flush()
                db.add(UserRole(user_id=user.id, role_id=role.id))
                db.commit()
                user = load_user(db, user.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User context is required")
    if not user.is_active or user.is_locked:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive or locked")
    return user


def get_current_permissions(user: User = Depends(get_current_user_stub)) -> set[str]:
    return permission_codes_for_user(user)


def audit_access_denied(db: Session, request: Request, user: User | None, permission_codes: tuple[str, ...]) -> None:
    path = request.url.path
    action = "ACCESS_DENIED_ADMIN" if "/admin" in path else "ACCESS_DENIED_CONTRACTOR" if "/contractor" in path else "ACCESS_DENIED_REQUEST"
    write_audit(
        db,
        action,
        "Permission",
        None,
        new_data={"path": path, "permissions": list(permission_codes)},
        actor_id=user.id if user else None,
        actor_type="RBAC",
    )
    db.commit()


def require_permission(permission_code: str):
    def dependency(
        request: Request,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user_stub),
        permissions: set[str] = Depends(get_current_permissions),
    ) -> User:
        if permission_code not in permissions:
            audit_access_denied(db, request, user, (permission_code,))
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return user

    return dependency


def require_any_permission(*permission_codes: str):
    def dependency(
        request: Request,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user_stub),
        permissions: set[str] = Depends(get_current_permissions),
    ) -> User:
        if not any(code in permissions for code in permission_codes):
            audit_access_denied(db, request, user, permission_codes)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return user

    return dependency


def require_all_permissions(*permission_codes: str):
    def dependency(
        request: Request,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user_stub),
        permissions: set[str] = Depends(get_current_permissions),
    ) -> User:
        if not all(code in permissions for code in permission_codes):
            audit_access_denied(db, request, user, permission_codes)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return user

    return dependency


def active_contractor_ids_for_user(user: User) -> set[UUID]:
    return {
        membership.contractor_id
        for membership in user.contractor_memberships
        if membership.is_active and membership.contractor is not None and membership.contractor.is_active
    }


def get_current_contractor_ids(
    user: User = Depends(require_permission("contractor.requests.view")),
) -> set[UUID]:
    ids = active_contractor_ids_for_user(user)
    if not ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contractor context not found")
    return ids


def require_contractor_permission(permission_code: str):
    def dependency(
        x_user_id: UUID | None = Header(default=None),
        x_contractor_id: UUID | None = Header(default=None),
        db: Session = Depends(get_db),
    ) -> ContractorAuthContext:
        # TODO: Remove X-Contractor-Id fallback when real contractor auth exists.
        if x_user_id is not None:
            user = get_current_user_stub(x_user_id=x_user_id, x_user_role=None, db=db)
            permissions = permission_codes_for_user(user)
            if permission_code not in permissions:
                write_audit(
                    db,
                    "ACCESS_DENIED_CONTRACTOR",
                    "Permission",
                    None,
                    new_data={"permissions": [permission_code]},
                    actor_id=user.id,
                    actor_type="RBAC",
                )
                db.commit()
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
            contractor_ids = active_contractor_ids_for_user(user)
            if not contractor_ids:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contractor context not found")
            return ContractorAuthContext(contractor_ids=contractor_ids, actor_id=user.id, user=user)
        if not dev_auth_enabled():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required")
        if x_contractor_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Contractor context is required")
        return ContractorAuthContext(contractor_ids={x_contractor_id}, actor_id=x_contractor_id, legacy_contractor_id=x_contractor_id)

    return dependency


def get_current_contractor_id(x_contractor_id: UUID | None = Header(default=None)) -> UUID:
    # TODO: Deprecated legacy fallback. Replace with User + ContractorMembership context.
    if not dev_auth_enabled():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required")
    if x_contractor_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Contractor context is required",
        )
    return x_contractor_id


def get_current_internal_actor_id(x_actor_id: UUID | None = Header(default=None)) -> UUID | None:
    # TODO: Replace this temporary stub with real Security Platform identity context.
    return x_actor_id


def get_current_internal_actor_id_from_user(
    x_actor_id: UUID | None = Header(default=None),
    user: User = Depends(get_current_user_stub),
) -> UUID:
    # TODO: Remove X-Actor-Id override when real user identity is available in all collaboration flows.
    return x_actor_id or user.id
