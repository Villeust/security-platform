from dataclasses import dataclass
from uuid import UUID

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.session import get_db
from app.models.admin import AuthSource, ContractorMembership, Role, RolePermission, User, UserRole, UserType
from app.services.audit_service import write_audit
from app.services.auth_service import session_from_access_cookie, token_hash
from app.services.rbac_service import permission_codes_for_user, seed_rbac


@dataclass(frozen=True)
class ContractorAuthContext:
    contractor_ids: set[UUID]
    actor_id: UUID | None
    user: User | None = None
    legacy_contractor_id: UUID | None = None
    primary_contractor_id: UUID | None = None
    permissions: set[str] | None = None
    roles: set[str] | None = None


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
    access_cookie: str | None = Cookie(default=None, alias=settings.auth_access_cookie_name),
    db: Session = Depends(get_db),
) -> User:
    seed_rbac(db)
    session = session_from_access_cookie(db, access_cookie)
    user: User | None = None
    if session is not None:
        user = load_user(db, session.user_id)
    if user is None and not dev_auth_enabled():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required")
    if user is None:
        user = load_user(db, x_user_id) if x_user_id is not None else None
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


def get_current_session(
    access_cookie: str | None = Cookie(default=None, alias=settings.auth_access_cookie_name),
    db: Session = Depends(get_db),
):
    session = session_from_access_cookie(db, access_cookie)
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required")
    return session


def require_full_session(
    access_cookie: str | None = Cookie(default=None, alias=settings.auth_access_cookie_name),
    db: Session = Depends(get_db),
) -> None:
    session = session_from_access_cookie(db, access_cookie)
    if session is not None and session.must_change_password:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PASSWORD_CHANGE_REQUIRED")


def require_csrf(
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    x_user_id: UUID | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
    x_contractor_id: UUID | None = Header(default=None),
    csrf_cookie: str | None = Cookie(default=None, alias=settings.auth_csrf_cookie_name),
    access_cookie: str | None = Cookie(default=None, alias=settings.auth_access_cookie_name),
    db: Session = Depends(get_db),
) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    session = session_from_access_cookie(db, access_cookie)
    dev_role_bypass = x_user_role is not None and (
        not request.url.path.startswith(f"{settings.api_v1_prefix}/admin/workflow-center") or x_user_role != "PLATFORM_ADMIN"
    )
    if session is None and dev_auth_enabled() and (x_user_id is not None or x_contractor_id is not None or dev_role_bypass):
        return
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required")
    if not x_csrf_token or not csrf_cookie or x_csrf_token != csrf_cookie:
        write_audit(db, "CSRF_REJECTED", "Request", None, actor_id=session.user_id, actor_type="SECURITY", new_data={"path": request.url.path})
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF_TOKEN_INVALID")
    if token_hash(x_csrf_token) != session.csrf_token_hash:
        write_audit(db, "CSRF_REJECTED", "Request", None, actor_id=session.user_id, actor_type="SECURITY", new_data={"path": request.url.path})
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF_TOKEN_INVALID")


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
        _: None = Depends(require_full_session),
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
        _: None = Depends(require_full_session),
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
        _: None = Depends(require_full_session),
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


def primary_contractor_id_for_user(user: User, contractor_ids: set[UUID]) -> UUID | None:
    for membership in user.contractor_memberships:
        if membership.is_primary and membership.contractor_id in contractor_ids:
            return membership.contractor_id
    return next(iter(contractor_ids), None)


def get_current_contractor_ids(
    user: User = Depends(require_permission("contractor.requests.view")),
) -> set[UUID]:
    ids = active_contractor_ids_for_user(user)
    if not ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contractor context not found")
    return ids


def require_contractor_permission(permission_code: str):
    def dependency(
        request: Request,
        x_user_id: UUID | None = Header(default=None),
        x_contractor_id: UUID | None = Header(default=None),
        access_cookie: str | None = Cookie(default=None, alias=settings.auth_access_cookie_name),
        db: Session = Depends(get_db),
    ) -> ContractorAuthContext:
        seed_rbac(db)
        session = session_from_access_cookie(db, access_cookie)
        user = load_user(db, session.user_id) if session is not None else None
        if user is None and x_user_id is not None and dev_auth_enabled():
            user = get_current_user_stub(x_user_id=x_user_id, x_user_role=None, access_cookie=None, db=db)

        if user is not None:
            if not user.is_active or user.is_locked or not user.authentication_enabled:
                audit_access_denied(db, request, user, (permission_code,))
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive or locked")
            if user.user_type != UserType.CONTRACTOR:
                audit_access_denied(db, request, user, (permission_code,))
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Contractor account is required")
            permissions = permission_codes_for_user(user)
            role_codes = {item.role.code for item in user.roles if item.role and item.role.is_active}
            if not role_codes.intersection({"CONTRACTOR_MANAGER", "CONTRACTOR_USER"}):
                audit_access_denied(db, request, user, (permission_code,))
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Contractor role is required")
            if permission_code not in permissions:
                audit_access_denied(db, request, user, (permission_code,))
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
            contractor_ids = active_contractor_ids_for_user(user)
            if not contractor_ids:
                write_audit(
                    db,
                    "CONTRACTOR_MEMBERSHIP_MISSING",
                    "ContractorMembership",
                    None,
                    new_data={"path": request.url.path},
                    actor_id=user.id,
                    actor_type="CONTRACTOR_PORTAL",
                )
                db.commit()
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contractor context not found")
            return ContractorAuthContext(
                contractor_ids=contractor_ids,
                actor_id=user.id,
                user=user,
                primary_contractor_id=primary_contractor_id_for_user(user, contractor_ids),
                permissions=permissions,
                roles=role_codes,
            )

        if not dev_auth_enabled():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required")
        if x_contractor_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Contractor context is required")
        return ContractorAuthContext(
            contractor_ids={x_contractor_id},
            actor_id=x_contractor_id,
            legacy_contractor_id=x_contractor_id,
            primary_contractor_id=x_contractor_id,
            permissions={permission_code},
            roles={"LEGACY_DEV_CONTRACTOR"},
        )

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
