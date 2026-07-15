from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.admin import AdminAuditLog, AuthSource, Role, User, UserType
from app.models.reference_data import City, Contractor, ContractorResponsibility, Facility, Premise, WorkType
from app.schemas.admin import (
    AdminAuditLogResponse,
    AdminDashboardResponse,
    AdminSystemStatusItem,
    AdminSystemStatusResponse,
    ContractorAdminCreate,
    ContractorAdminResponse,
    ContractorAdminUpdate,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
    UserContractorsUpdate,
    UserCreate,
    UserResponse,
    UserRolesUpdate,
    UserUpdate,
)
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

router = APIRouter(prefix="/admin", tags=["admin"])


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
        role_ids=[item.role_id for item in user.roles],
        role_codes=[item.role.code for item in user.roles if item.role is not None],
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
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.get("/dashboard", response_model=AdminDashboardResponse, summary="Get admin dashboard")
def get_admin_dashboard(db: Session = Depends(get_db)) -> AdminDashboardResponse:
    return AdminDashboardResponse(**dashboard_counts(db))


@router.get("/system-status", response_model=AdminSystemStatusResponse, summary="Get admin system status")
def get_admin_system_status(db: Session = Depends(get_db)) -> AdminSystemStatusResponse:
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
    search: str | None = None,
    is_active: bool | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> list[ContractorAdminResponse]:
    return [serialize_contractor(item, db) for item in list_contractors(db, search, is_active, skip, limit)]


@router.post("/contractors", response_model=ContractorAdminResponse, status_code=status.HTTP_201_CREATED, summary="Create admin contractor")
def admin_create_contractor(payload: ContractorAdminCreate, db: Session = Depends(get_db)) -> ContractorAdminResponse:
    return serialize_contractor(create_contractor(db, payload), db)


@router.get("/contractors/{item_id}", response_model=ContractorAdminResponse, summary="Get admin contractor")
def admin_get_contractor(item_id: UUID, db: Session = Depends(get_db)) -> ContractorAdminResponse:
    return serialize_contractor(get_or_404(db, Contractor, item_id), db)


@router.patch("/contractors/{item_id}", response_model=ContractorAdminResponse, summary="Update admin contractor")
def admin_update_contractor(item_id: UUID, payload: ContractorAdminUpdate, db: Session = Depends(get_db)) -> ContractorAdminResponse:
    return serialize_contractor(update_contractor(db, item_id, payload), db)


@router.post("/contractors/{item_id}/deactivate", response_model=ContractorAdminResponse, summary="Deactivate contractor")
def admin_deactivate_contractor(item_id: UUID, db: Session = Depends(get_db)) -> ContractorAdminResponse:
    return serialize_contractor(set_contractor_active(db, item_id, False), db)


@router.post("/contractors/{item_id}/activate", response_model=ContractorAdminResponse, summary="Activate contractor")
def admin_activate_contractor(item_id: UUID, db: Session = Depends(get_db)) -> ContractorAdminResponse:
    return serialize_contractor(set_contractor_active(db, item_id, True), db)


@router.get("/users", response_model=list[UserResponse], summary="List admin users")
def admin_list_users(
    db: Session = Depends(get_db),
    search: str | None = None,
    user_type: UserType | None = None,
    role_id: UUID | None = None,
    contractor_id: UUID | None = None,
    is_active: bool | None = None,
    is_locked: bool | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> list[UserResponse]:
    return [serialize_user(item) for item in list_users(db, search, user_type, role_id, contractor_id, is_active, is_locked, skip, limit)]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="Create admin user")
def admin_create_user(payload: UserCreate, db: Session = Depends(get_db)) -> UserResponse:
    ensure_seed_roles(db)
    return serialize_user(create_user(db, payload))


@router.get("/users/{item_id}", response_model=UserResponse, summary="Get admin user")
def admin_get_user(item_id: UUID, db: Session = Depends(get_db)) -> UserResponse:
    return serialize_user(get_or_404(db, User, item_id))


@router.patch("/users/{item_id}", response_model=UserResponse, summary="Update admin user")
def admin_update_user(item_id: UUID, payload: UserUpdate, db: Session = Depends(get_db)) -> UserResponse:
    return serialize_user(update_user(db, item_id, payload))


@router.post("/users/{item_id}/deactivate", response_model=UserResponse, summary="Deactivate admin user")
def admin_deactivate_user(item_id: UUID, db: Session = Depends(get_db)) -> UserResponse:
    return serialize_user(set_user_active(db, item_id, False))


@router.post("/users/{item_id}/activate", response_model=UserResponse, summary="Activate admin user")
def admin_activate_user(item_id: UUID, db: Session = Depends(get_db)) -> UserResponse:
    return serialize_user(set_user_active(db, item_id, True))


@router.put("/users/{item_id}/roles", response_model=UserResponse, summary="Set user roles")
def admin_set_user_roles(item_id: UUID, payload: UserRolesUpdate, db: Session = Depends(get_db)) -> UserResponse:
    return serialize_user(set_user_roles(db, item_id, payload))


@router.put("/users/{item_id}/contractors", response_model=UserResponse, summary="Set user contractor memberships")
def admin_set_user_contractors(item_id: UUID, payload: UserContractorsUpdate, db: Session = Depends(get_db)) -> UserResponse:
    return serialize_user(set_user_contractors(db, item_id, payload))


@router.get("/roles", response_model=list[RoleResponse], summary="List roles")
def admin_list_roles(
    db: Session = Depends(get_db),
    search: str | None = None,
    is_active: bool | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> list[RoleResponse]:
    return [serialize_role(item) for item in list_roles(db, search, is_active, skip, limit)]


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED, summary="Create role")
def admin_create_role(payload: RoleCreate, db: Session = Depends(get_db)) -> RoleResponse:
    return serialize_role(create_role(db, payload))


@router.patch("/roles/{item_id}", response_model=RoleResponse, summary="Update role")
def admin_update_role(item_id: UUID, payload: RoleUpdate, db: Session = Depends(get_db)) -> RoleResponse:
    return serialize_role(update_role(db, item_id, payload))


@router.post("/roles/{item_id}/deactivate", response_model=RoleResponse, summary="Deactivate role")
def admin_deactivate_role(item_id: UUID, db: Session = Depends(get_db)) -> RoleResponse:
    return serialize_role(deactivate_role(db, item_id))


@router.get("/audit", response_model=list[AdminAuditLogResponse], summary="List admin audit")
def admin_list_audit(
    db: Session = Depends(get_db),
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
def admin_list_cities(db: Session = Depends(get_db), search: str | None = None, is_active: bool | None = None, skip: int = 0, limit: int = 100) -> list[City]:
    return list(db.scalars(apply_admin_filters(select(City), City, search, is_active).order_by(City.name).offset(skip).limit(limit)).all())


@router.post("/cities", response_model=CityResponse, status_code=status.HTTP_201_CREATED)
def admin_create_city(payload: CityCreate, db: Session = Depends(get_db)) -> City:
    return admin_create_reference(db, City, payload, "CITY_CREATED", "City")


@router.patch("/cities/{item_id}", response_model=CityResponse)
def admin_update_city(item_id: UUID, payload: CityUpdate, db: Session = Depends(get_db)) -> City:
    return admin_update_reference(db, City, item_id, payload, "CITY_UPDATED", "City")


@router.get("/facilities", response_model=list[FacilityResponse])
def admin_list_facilities(db: Session = Depends(get_db), search: str | None = None, is_active: bool | None = None, city_id: UUID | None = None, skip: int = 0, limit: int = 100) -> list[Facility]:
    query = apply_admin_filters(select(Facility), Facility, search, is_active)
    if city_id is not None:
        query = query.where(Facility.city_id == city_id)
    return list(db.scalars(query.order_by(Facility.name).offset(skip).limit(limit)).all())


@router.post("/facilities", response_model=FacilityResponse, status_code=status.HTTP_201_CREATED)
def admin_create_facility(payload: FacilityCreate, db: Session = Depends(get_db)) -> Facility:
    return admin_create_reference(db, Facility, payload, "FACILITY_CREATED", "Facility")


@router.patch("/facilities/{item_id}", response_model=FacilityResponse)
def admin_update_facility(item_id: UUID, payload: FacilityUpdate, db: Session = Depends(get_db)) -> Facility:
    return admin_update_reference(db, Facility, item_id, payload, "FACILITY_UPDATED", "Facility")


@router.get("/premises", response_model=list[PremiseResponse])
def admin_list_premises(db: Session = Depends(get_db), search: str | None = None, is_active: bool | None = None, facility_id: UUID | None = None, skip: int = 0, limit: int = 100) -> list[Premise]:
    query = select(Premise)
    if search:
        query = query.where(Premise.name.ilike(f"%{search}%"))
    if is_active is not None:
        query = query.where(Premise.is_active == is_active)
    if facility_id is not None:
        query = query.where(Premise.facility_id == facility_id)
    return list(db.scalars(query.order_by(Premise.name).offset(skip).limit(limit)).all())


@router.post("/premises", response_model=PremiseResponse, status_code=status.HTTP_201_CREATED)
def admin_create_premise(payload: PremiseCreate, db: Session = Depends(get_db)) -> Premise:
    return admin_create_reference(db, Premise, payload, "PREMISE_CREATED", "Premise")


@router.patch("/premises/{item_id}", response_model=PremiseResponse)
def admin_update_premise(item_id: UUID, payload: PremiseUpdate, db: Session = Depends(get_db)) -> Premise:
    return admin_update_reference(db, Premise, item_id, payload, "PREMISE_UPDATED", "Premise")


@router.get("/work-types", response_model=list[WorkTypeResponse])
def admin_list_work_types(db: Session = Depends(get_db), search: str | None = None, is_active: bool | None = None, skip: int = 0, limit: int = 100) -> list[WorkType]:
    return list(db.scalars(apply_admin_filters(select(WorkType), WorkType, search, is_active).order_by(WorkType.name).offset(skip).limit(limit)).all())


@router.post("/work-types", response_model=WorkTypeResponse, status_code=status.HTTP_201_CREATED)
def admin_create_work_type(payload: WorkTypeCreate, db: Session = Depends(get_db)) -> WorkType:
    return admin_create_reference(db, WorkType, payload, "WORK_TYPE_UPDATED", "WorkType")


@router.patch("/work-types/{item_id}", response_model=WorkTypeResponse)
def admin_update_work_type(item_id: UUID, payload: WorkTypeUpdate, db: Session = Depends(get_db)) -> WorkType:
    return admin_update_reference(db, WorkType, item_id, payload, "WORK_TYPE_UPDATED", "WorkType")


@router.get("/responsibilities", response_model=list[ContractorResponsibilityResponse])
def admin_list_responsibilities(
    db: Session = Depends(get_db),
    contractor_id: UUID | None = None,
    city_id: UUID | None = None,
    facility_id: UUID | None = None,
    work_type_id: UUID | None = None,
    is_active: bool | None = None,
    skip: int = 0,
    limit: int = 100,
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
def admin_create_responsibility(payload: ContractorResponsibilityCreate, db: Session = Depends(get_db)) -> ContractorResponsibility:
    return admin_create_reference(db, ContractorResponsibility, payload, "RESPONSIBILITY_CREATED", "ContractorResponsibility")


@router.patch("/responsibilities/{item_id}", response_model=ContractorResponsibilityResponse)
def admin_update_responsibility(item_id: UUID, payload: ContractorResponsibilityUpdate, db: Session = Depends(get_db)) -> ContractorResponsibility:
    return admin_update_reference(db, ContractorResponsibility, item_id, payload, "RESPONSIBILITY_UPDATED", "ContractorResponsibility")
