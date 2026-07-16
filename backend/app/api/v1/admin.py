from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.api.deps import get_current_user_stub, require_csrf, require_permission
from app.db.session import get_db
from app.models.admin import AdminAuditLog, AdminNotification, AdminNotificationSeverity, AdminNotificationType, AuthSource, LockReason, Permission, Role, User, UserType
from app.models.reference_data import City, Contractor, ContractorResponsibility, Facility, Premise, WorkType, utc_now
from app.schemas.admin import (
    AdminAuditLogResponse,
    AdminDashboardResponse,
    AdminNotificationResponse,
    AdminSystemStatusItem,
    AdminSystemStatusResponse,
    ContractorAdminCreate,
    ContractorAdminResponse,
    ContractorAdminUpdate,
    PermissionResponse,
    RoleCreate,
    RolePermissionsUpdate,
    RoleResponse,
    RoleUpdate,
    UserContractorsUpdate,
    UserCreate,
    UserCreateResponse,
    UserLockRequest,
    UserUnlockRequest,
    UserResponse,
    UserRolesUpdate,
    UserUpdate,
)
from app.services.rbac_service import get_role_permissions, list_permissions, permission_codes_for_user, set_role_permissions
from app.schemas.reference_data import (
    CityCreate,
    CityResponse,
    CityUpdate,
    ContractorResponsibilityCreate,
    ContractorResponsibilityResponse,
    ContractorResponsibilityUpdate,
    FacilityCreate,
    FacilityResponse,
    FacilityUpdate,
    PremiseCreate,
    PremiseResponse,
    PremiseUpdate,
    WorkTypeCreate,
    WorkTypeResponse,
    WorkTypeUpdate,
)
from app.services.admin_service import (
    contractor_counts,
    create_contractor,
    create_role,
    create_user,
    dashboard_counts,
    deactivate_role,
    ensure_seed_roles,
    get_or_404,
    list_contractors,
    list_roles,
    list_users,
    set_contractor_active,
    set_user_active,
    set_user_contractors,
    set_user_roles,
    update_contractor,
    update_role,
    update_user,
)
from app.services.audit_service import write_audit
from app.services.auth_service import revoke_all_sessions, set_temporary_password
from app.services.notification_service import create_notification, list_notifications, mark_read, resolve_notification
from app.services.password_service import generate_temporary_password

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_csrf)])


def json_safe(value: Any) -> Any:
    if isinstance(value, UUID | datetime | Enum):
        return str(value)
    return value


def serialize_user(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        user_type=user.user_type,
        auth_source=user.auth_source,
        is_active=user.is_active,
        is_locked=user.is_locked,
        last_login_at=user.last_login_at,
        password_changed_at=user.password_changed_at,
        must_change_password=user.must_change_password,
        failed_login_attempts=user.failed_login_attempts,
        locked_until=user.locked_until,
        last_login_ip=user.last_login_ip,
        external_subject=user.external_subject,
        external_directory_id=user.external_directory_id,
        authentication_enabled=user.authentication_enabled,
        password_expires_at=user.password_expires_at,
        password_expired_at=user.password_expired_at,
        password_expiry_notified_at=user.password_expiry_notified_at,
        lock_reason=user.lock_reason,
        locked_at=user.locked_at,
        locked_by_id=user.locked_by_id,
        unlock_reason=user.unlock_reason,
        role_ids=[item.role_id for item in user.roles],
        role_codes=[item.role.code for item in user.roles if item.role is not None],
        permissions=sorted(permission_codes_for_user(user)),
        contractor_memberships=user.contractor_memberships,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def serialize_contractor(contractor: Contractor, db: Session) -> ContractorAdminResponse:
    users_count, responsibilities_count = contractor_counts(db, contractor.id)
    return ContractorAdminResponse(
        id=contractor.id,
        name=contractor.name,
        code=contractor.code,
        email=contractor.email,
        phone=contractor.phone,
        is_active=contractor.is_active,
        users_count=users_count,
        responsibilities_count=responsibilities_count,
        created_at=contractor.created_at,
        updated_at=contractor.updated_at,
    )


def serialize_role(role: Role) -> RoleResponse:
    return RoleResponse(
        id=role.id,
        code=role.code,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        is_active=role.is_active,
        users_count=len(role.users),
        permissions_count=len(role.permissions),
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


def serialize_permission(permission: Permission) -> PermissionResponse:
    return PermissionResponse.model_validate(permission)


@router.get("/me", response_model=UserResponse, summary="Get current admin/auth context")
def admin_me(user: User = Depends(get_current_user_stub)) -> UserResponse:
    return serialize_user(user)


@router.get("/dev-users", response_model=list[UserResponse], summary="List development seed users")
def admin_dev_users(db: Session = Depends(get_db)) -> list[UserResponse]:
    if settings.environment.lower() in {"production", "prod"} or not settings.allow_dev_auth_headers:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    users = db.scalars(
        select(User)
        .where(User.username.in_([
            "dev.platform.admin",
            "dev.security.admin",
            "dev.security.operator",
            "dev.contractor.manager",
            "dev.contractor.user",
            "dev.viewer",
        ]))
        .order_by(User.username)
    ).all()
    return [serialize_user(user) for user in users]


@router.get("/dashboard", response_model=AdminDashboardResponse, summary="Get admin dashboard")
def get_admin_dashboard(db: Session = Depends(get_db), _: User = Depends(require_permission("admin.dashboard.view"))) -> AdminDashboardResponse:
    return AdminDashboardResponse(**dashboard_counts(db))


@router.get("/system-status", response_model=AdminSystemStatusResponse, summary="Get admin system status")
def get_admin_system_status(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("admin.system_status.view")),
) -> AdminSystemStatusResponse:
    database_status = "operational"
    try:
        db.execute(select(1))
    except Exception:
        database_status = "degraded"
    return AdminSystemStatusResponse(
        backend=AdminSystemStatusItem(status="operational", description="Backend API responds locally."),
        database=AdminSystemStatusItem(status=database_status, description="Database connection checked locally."),
        frontend_configured=AdminSystemStatusItem(status="configured", description="Frontend is configured through VITE_API_URL."),
        email_configured=AdminSystemStatusItem(status="not_configured", description="Email notifications are planned for a later stage."),
        adfs_configured=AdminSystemStatusItem(status="not_configured", description="ADFS integration is planned for a later stage."),
        contractor_portal_status=AdminSystemStatusItem(status="planned", description="Contractor Portal is not implemented yet."),
    )


@router.get("/contractors", response_model=list[ContractorAdminResponse], summary="List admin contractors")
def admin_list_contractors(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("admin.contractors.view")),
    search: str | None = Query(default=None, max_length=settings.max_search_length),
    is_active: bool | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> list[ContractorAdminResponse]:
    return [serialize_contractor(item, db) for item in list_contractors(db, search, is_active, skip, limit)]


@router.post("/contractors", response_model=ContractorAdminResponse, status_code=status.HTTP_201_CREATED, summary="Create admin contractor")
def admin_create_contractor(payload: ContractorAdminCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("admin.contractors.manage"))) -> ContractorAdminResponse:
    return serialize_contractor(create_contractor(db, payload), db)


@router.get("/contractors/{item_id}", response_model=ContractorAdminResponse, summary="Get admin contractor")
def admin_get_contractor(item_id: UUID, db: Session = Depends(get_db), _: User = Depends(require_permission("admin.contractors.view"))) -> ContractorAdminResponse:
    return serialize_contractor(get_or_404(db, Contractor, item_id), db)


@router.patch("/contractors/{item_id}", response_model=ContractorAdminResponse, summary="Update admin contractor")
def admin_update_contractor(item_id: UUID, payload: ContractorAdminUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("admin.contractors.manage"))) -> ContractorAdminResponse:
    return serialize_contractor(update_contractor(db, item_id, payload), db)


@router.post("/contractors/{item_id}/deactivate", response_model=ContractorAdminResponse, summary="Deactivate contractor")
def admin_deactivate_contractor(item_id: UUID, db: Session = Depends(get_db), _: User = Depends(require_permission("admin.contractors.manage"))) -> ContractorAdminResponse:
    return serialize_contractor(set_contractor_active(db, item_id, False), db)


@router.post("/contractors/{item_id}/activate", response_model=ContractorAdminResponse, summary="Activate contractor")
def admin_activate_contractor(item_id: UUID, db: Session = Depends(get_db), _: User = Depends(require_permission("admin.contractors.manage"))) -> ContractorAdminResponse:
    return serialize_contractor(set_contractor_active(db, item_id, True), db)


@router.get("/users", response_model=list[UserResponse], summary="List admin users")
def admin_list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("admin.users.view")),
    search: str | None = Query(default=None, max_length=settings.max_search_length),
    user_type: UserType | None = None,
    role_id: UUID | None = None,
    contractor_id: UUID | None = None,
    is_active: bool | None = None,
    is_locked: bool | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> list[UserResponse]:
    return [serialize_user(item) for item in list_users(db, search, user_type, role_id, contractor_id, is_active, is_locked, skip, limit)]


@router.post("/users", response_model=UserCreateResponse, status_code=status.HTTP_201_CREATED, summary="Create admin user")
def admin_create_user(payload: UserCreate, db: Session = Depends(get_db), actor: User = Depends(require_permission("admin.users.manage"))) -> UserCreateResponse:
    ensure_seed_roles(db)
    user = create_user(db, payload)
    temporary_password = None
    if user.auth_source == AuthSource.LOCAL:
        temporary_password = payload.temporary_password or generate_temporary_password()
        set_temporary_password(db, user, temporary_password, actor_id=actor.id)
        db.commit()
        user = get_or_404(db, User, user.id)
    return UserCreateResponse(**serialize_user(user).model_dump(), temporary_password=temporary_password)


@router.get("/users/{item_id}", response_model=UserResponse, summary="Get admin user")
def admin_get_user(item_id: UUID, db: Session = Depends(get_db), _: User = Depends(require_permission("admin.users.view"))) -> UserResponse:
    return serialize_user(get_or_404(db, User, item_id))


@router.patch("/users/{item_id}", response_model=UserResponse, summary="Update admin user")
def admin_update_user(item_id: UUID, payload: UserUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("admin.users.manage"))) -> UserResponse:
    return serialize_user(update_user(db, item_id, payload))


@router.post("/users/{item_id}/deactivate", response_model=UserResponse, summary="Deactivate admin user")
def admin_deactivate_user(item_id: UUID, db: Session = Depends(get_db), _: User = Depends(require_permission("admin.users.manage"))) -> UserResponse:
    return serialize_user(set_user_active(db, item_id, False))


@router.post("/users/{item_id}/activate", response_model=UserResponse, summary="Activate admin user")
def admin_activate_user(item_id: UUID, db: Session = Depends(get_db), _: User = Depends(require_permission("admin.users.manage"))) -> UserResponse:
    return serialize_user(set_user_active(db, item_id, True))


@router.post("/users/{item_id}/lock", response_model=UserResponse, summary="Lock user")
def admin_lock_user(item_id: UUID, payload: UserLockRequest, db: Session = Depends(get_db), actor: User = Depends(require_permission("admin.users.security.manage"))) -> UserResponse:
    if actor.id == item_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot lock yourself")
    user = get_or_404(db, User, item_id)
    user.is_locked = True
    user.lock_reason = LockReason.ADMINISTRATIVE
    user.locked_at = utc_now()
    user.locked_by_id = actor.id
    if payload.revoke_sessions:
        revoke_all_sessions(db, user.id, "locked_by_admin")
    write_audit(db, "USER_ACCOUNT_LOCKED_BY_ADMIN", "User", user.id, actor_id=actor.id, new_data={"reason": payload.reason, "comment": payload.comment})
    create_notification(
        db,
        AdminNotificationType.USER_ACCOUNT_LOCKED,
        AdminNotificationSeverity.HIGH,
        "Учётная запись заблокирована",
        f"Пользователь {user.username} заблокирован администратором.",
        user_id=user.id,
        details={"actor_id": str(actor.id), "comment": payload.comment},
    )
    db.commit()
    db.refresh(user)
    return serialize_user(user)


@router.post("/users/{item_id}/unlock", response_model=UserResponse, summary="Unlock user")
def admin_unlock_user(item_id: UUID, payload: UserUnlockRequest, db: Session = Depends(get_db), actor: User = Depends(require_permission("admin.users.security.manage"))) -> UserResponse:
    user = get_or_404(db, User, item_id)
    user.is_locked = False
    user.locked_until = None
    user.lock_reason = None
    user.failed_login_attempts = 0
    user.unlock_reason = payload.comment
    write_audit(db, "USER_ACCOUNT_UNLOCKED", "User", user.id, actor_id=actor.id, new_data={"comment": payload.comment})
    create_notification(db, AdminNotificationType.USER_ACCOUNT_UNLOCKED, AdminNotificationSeverity.INFO, "Учётная запись разблокирована", f"Пользователь {user.username} разблокирован.", user_id=user.id)
    db.commit()
    db.refresh(user)
    return serialize_user(user)


@router.post("/users/{item_id}/generate-temporary-password", response_model=UserCreateResponse, summary="Generate temporary password")
def admin_generate_temporary_password(item_id: UUID, db: Session = Depends(get_db), actor: User = Depends(require_permission("admin.users.credentials.manage"))) -> UserCreateResponse:
    user = get_or_404(db, User, item_id)
    temporary_password = generate_temporary_password()
    set_temporary_password(db, user, temporary_password, actor_id=actor.id)
    db.commit()
    db.refresh(user)
    return UserCreateResponse(**serialize_user(user).model_dump(), temporary_password=temporary_password)


@router.put("/users/{item_id}/roles", response_model=UserResponse, summary="Set user roles")
def admin_set_user_roles(item_id: UUID, payload: UserRolesUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("admin.users.manage"))) -> UserResponse:
    return serialize_user(set_user_roles(db, item_id, payload))


@router.put("/users/{item_id}/contractors", response_model=UserResponse, summary="Set user contractor memberships")
def admin_set_user_contractors(item_id: UUID, payload: UserContractorsUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("admin.users.manage"))) -> UserResponse:
    return serialize_user(set_user_contractors(db, item_id, payload))


@router.get("/roles", response_model=list[RoleResponse], summary="List roles")
def admin_list_roles(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("admin.roles.view")),
    search: str | None = Query(default=None, max_length=settings.max_search_length),
    is_active: bool | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> list[RoleResponse]:
    return [serialize_role(item) for item in list_roles(db, search, is_active, skip, limit)]


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED, summary="Create role")
def admin_create_role(payload: RoleCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("admin.roles.manage"))) -> RoleResponse:
    return serialize_role(create_role(db, payload))


@router.patch("/roles/{item_id}", response_model=RoleResponse, summary="Update role")
def admin_update_role(item_id: UUID, payload: RoleUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("admin.roles.manage"))) -> RoleResponse:
    return serialize_role(update_role(db, item_id, payload))


@router.post("/roles/{item_id}/deactivate", response_model=RoleResponse, summary="Deactivate role")
def admin_deactivate_role(item_id: UUID, db: Session = Depends(get_db), _: User = Depends(require_permission("admin.roles.manage"))) -> RoleResponse:
    return serialize_role(deactivate_role(db, item_id))


@router.get("/permissions", response_model=list[PermissionResponse], summary="List permissions")
def admin_list_permissions(db: Session = Depends(get_db), _: User = Depends(require_permission("admin.roles.view"))) -> list[PermissionResponse]:
    return [serialize_permission(permission) for permission in list_permissions(db)]


@router.get("/roles/{role_id}/permissions", response_model=list[PermissionResponse], summary="Get role permissions")
def admin_get_role_permissions(role_id: UUID, db: Session = Depends(get_db), _: User = Depends(require_permission("admin.roles.view"))) -> list[PermissionResponse]:
    return [serialize_permission(permission) for permission in get_role_permissions(db, role_id)]


@router.put("/roles/{role_id}/permissions", response_model=list[PermissionResponse], summary="Set role permissions")
def admin_set_role_permissions(
    role_id: UUID,
    payload: RolePermissionsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("admin.roles.manage")),
) -> list[PermissionResponse]:
    return [serialize_permission(permission) for permission in set_role_permissions(db, role_id, payload.permission_ids, actor_id=user.id)]


@router.get("/audit", response_model=list[AdminAuditLogResponse], summary="List admin audit")
def admin_list_audit(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("admin.audit.view")),
    actor_id: UUID | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> list[AdminAuditLog]:
    query = select(AdminAuditLog)
    if actor_id is not None:
        query = query.where(AdminAuditLog.actor_id == actor_id)
    if action:
        query = query.where(AdminAuditLog.action == action)
    if entity_type:
        query = query.where(AdminAuditLog.entity_type == entity_type)
    if entity_id is not None:
        query = query.where(AdminAuditLog.entity_id == entity_id)
    if created_from is not None:
        query = query.where(AdminAuditLog.created_at >= created_from)
    if created_to is not None:
        query = query.where(AdminAuditLog.created_at <= created_to)
    return list(db.scalars(query.order_by(AdminAuditLog.created_at.desc()).offset(skip).limit(limit)).all())


@router.get("/notifications", response_model=list[AdminNotificationResponse], summary="List admin notifications")
def admin_list_notifications(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("admin.notifications.view")),
    type: AdminNotificationType | None = None,
    severity: AdminNotificationSeverity | None = None,
    is_read: bool | None = None,
    is_resolved: bool | None = None,
    user_id: UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> list[AdminNotification]:
    return list_notifications(db, type, severity, is_read, is_resolved, user_id, created_from, created_to, skip, limit)


@router.get("/notifications/unread-count", summary="Get unread notifications count")
def admin_unread_notifications_count(db: Session = Depends(get_db), _: User = Depends(require_permission("admin.notifications.view"))) -> dict[str, int]:
    count = len(list_notifications(db, is_read=False, is_resolved=False, limit=1000))
    return {"count": count}


@router.post("/notifications/{notification_id}/read", response_model=AdminNotificationResponse)
def admin_mark_notification_read(notification_id: UUID, db: Session = Depends(get_db), actor: User = Depends(require_permission("admin.notifications.view"))) -> AdminNotification:
    notification = db.get(AdminNotification, notification_id)
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return mark_read(db, notification, actor.id)


@router.post("/notifications/{notification_id}/resolve", response_model=AdminNotificationResponse)
def admin_resolve_notification(notification_id: UUID, db: Session = Depends(get_db), actor: User = Depends(require_permission("admin.notifications.manage"))) -> AdminNotification:
    notification = db.get(AdminNotification, notification_id)
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return resolve_notification(db, notification, actor.id)


def admin_create_reference(db: Session, model: type[Any], payload: Any, action: str, entity_type: str) -> Any:
    item = model(**payload.model_dump())
    db.add(item)
    db.flush()
    write_audit(db, action, entity_type, item.id, new_data=payload.model_dump(mode="json"))
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Record violates a database constraint") from exc
    db.refresh(item)
    return item


def admin_update_reference(db: Session, model: type[Any], item_id: UUID, payload: Any, action: str, entity_type: str) -> Any:
    item = get_or_404(db, model, item_id)
    old = {key: json_safe(getattr(item, key)) for key in payload.model_dump(exclude_unset=True)}
    values = payload.model_dump(exclude_unset=True)
    for field, value in values.items():
        setattr(item, field, value)
    write_audit(db, action, entity_type, item.id, old_data=old, new_data=payload.model_dump(exclude_unset=True, mode="json"))
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Record violates a database constraint") from exc
    db.refresh(item)
    return item


def apply_admin_filters(query: Select[tuple[Any]], model: type[Any], search: str | None, is_active: bool | None) -> Select[tuple[Any]]:
    if search:
        pattern = f"%{search}%"
        columns = [getattr(model, name) for name in ("name", "code") if hasattr(model, name)]
        if columns:
            condition = columns[0].ilike(pattern)
            for column in columns[1:]:
                condition = condition | column.ilike(pattern)
            query = query.where(condition)
    if is_active is not None and hasattr(model, "is_active"):
        query = query.where(model.is_active == is_active)
    return query


@router.get("/cities", response_model=list[CityResponse])
def admin_list_cities(db: Session = Depends(get_db), _: User = Depends(require_permission("reference_data.manage")), search: str | None = Query(default=None, max_length=settings.max_search_length), is_active: bool | None = None, skip: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=100)) -> list[City]:
    return list(db.scalars(apply_admin_filters(select(City), City, search, is_active).order_by(City.name).offset(skip).limit(limit)).all())


@router.post("/cities", response_model=CityResponse, status_code=status.HTTP_201_CREATED)
def admin_create_city(payload: CityCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("reference_data.manage"))) -> City:
    return admin_create_reference(db, City, payload, "CITY_CREATED", "City")


@router.patch("/cities/{item_id}", response_model=CityResponse)
def admin_update_city(item_id: UUID, payload: CityUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("reference_data.manage"))) -> City:
    return admin_update_reference(db, City, item_id, payload, "CITY_UPDATED", "City")


@router.get("/facilities", response_model=list[FacilityResponse])
def admin_list_facilities(db: Session = Depends(get_db), _: User = Depends(require_permission("reference_data.manage")), search: str | None = Query(default=None, max_length=settings.max_search_length), is_active: bool | None = None, city_id: UUID | None = None, skip: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=100)) -> list[Facility]:
    query = apply_admin_filters(select(Facility), Facility, search, is_active)
    if city_id is not None:
        query = query.where(Facility.city_id == city_id)
    return list(db.scalars(query.order_by(Facility.name).offset(skip).limit(limit)).all())


@router.post("/facilities", response_model=FacilityResponse, status_code=status.HTTP_201_CREATED)
def admin_create_facility(payload: FacilityCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("reference_data.manage"))) -> Facility:
    return admin_create_reference(db, Facility, payload, "FACILITY_CREATED", "Facility")


@router.patch("/facilities/{item_id}", response_model=FacilityResponse)
def admin_update_facility(item_id: UUID, payload: FacilityUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("reference_data.manage"))) -> Facility:
    return admin_update_reference(db, Facility, item_id, payload, "FACILITY_UPDATED", "Facility")


@router.get("/premises", response_model=list[PremiseResponse])
def admin_list_premises(db: Session = Depends(get_db), _: User = Depends(require_permission("reference_data.manage")), search: str | None = Query(default=None, max_length=settings.max_search_length), is_active: bool | None = None, facility_id: UUID | None = None, skip: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=100)) -> list[Premise]:
    query = select(Premise)
    if search:
        query = query.where(Premise.name.ilike(f"%{search}%"))
    if is_active is not None:
        query = query.where(Premise.is_active == is_active)
    if facility_id is not None:
        query = query.where(Premise.facility_id == facility_id)
    return list(db.scalars(query.order_by(Premise.name).offset(skip).limit(limit)).all())


@router.post("/premises", response_model=PremiseResponse, status_code=status.HTTP_201_CREATED)
def admin_create_premise(payload: PremiseCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("reference_data.manage"))) -> Premise:
    return admin_create_reference(db, Premise, payload, "PREMISE_CREATED", "Premise")


@router.patch("/premises/{item_id}", response_model=PremiseResponse)
def admin_update_premise(item_id: UUID, payload: PremiseUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("reference_data.manage"))) -> Premise:
    return admin_update_reference(db, Premise, item_id, payload, "PREMISE_UPDATED", "Premise")


@router.get("/work-types", response_model=list[WorkTypeResponse])
def admin_list_work_types(db: Session = Depends(get_db), _: User = Depends(require_permission("reference_data.manage")), search: str | None = Query(default=None, max_length=settings.max_search_length), is_active: bool | None = None, skip: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=100)) -> list[WorkType]:
    return list(db.scalars(apply_admin_filters(select(WorkType), WorkType, search, is_active).order_by(WorkType.name).offset(skip).limit(limit)).all())


@router.post("/work-types", response_model=WorkTypeResponse, status_code=status.HTTP_201_CREATED)
def admin_create_work_type(payload: WorkTypeCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("reference_data.manage"))) -> WorkType:
    return admin_create_reference(db, WorkType, payload, "WORK_TYPE_UPDATED", "WorkType")


@router.patch("/work-types/{item_id}", response_model=WorkTypeResponse)
def admin_update_work_type(item_id: UUID, payload: WorkTypeUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("reference_data.manage"))) -> WorkType:
    return admin_update_reference(db, WorkType, item_id, payload, "WORK_TYPE_UPDATED", "WorkType")


@router.get("/responsibilities", response_model=list[ContractorResponsibilityResponse])
def admin_list_responsibilities(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reference_data.manage")),
    contractor_id: UUID | None = None,
    city_id: UUID | None = None,
    facility_id: UUID | None = None,
    work_type_id: UUID | None = None,
    is_active: bool | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> list[ContractorResponsibility]:
    query = select(ContractorResponsibility)
    for column, value in (
        (ContractorResponsibility.contractor_id, contractor_id),
        (ContractorResponsibility.city_id, city_id),
        (ContractorResponsibility.facility_id, facility_id),
        (ContractorResponsibility.work_type_id, work_type_id),
    ):
        if value is not None:
            query = query.where(column == value)
    if is_active is not None:
        query = query.where(ContractorResponsibility.is_active == is_active)
    return list(db.scalars(query.order_by(ContractorResponsibility.priority).offset(skip).limit(limit)).all())


@router.post("/responsibilities", response_model=ContractorResponsibilityResponse, status_code=status.HTTP_201_CREATED)
def admin_create_responsibility(payload: ContractorResponsibilityCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("reference_data.manage"))) -> ContractorResponsibility:
    return admin_create_reference(db, ContractorResponsibility, payload, "RESPONSIBILITY_CREATED", "ContractorResponsibility")


@router.patch("/responsibilities/{item_id}", response_model=ContractorResponsibilityResponse)
def admin_update_responsibility(item_id: UUID, payload: ContractorResponsibilityUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("reference_data.manage"))) -> ContractorResponsibility:
    return admin_update_reference(db, ContractorResponsibility, item_id, payload, "RESPONSIBILITY_UPDATED", "ContractorResponsibility")
