from collections.abc import Sequence
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.admin import AuthSource, ContractorMembership, Role, User, UserRole, UserType
from app.models.reference_data import City, Contractor, ContractorResponsibility, Facility, Premise, WorkType
from app.models.requests import ContractorRequest, RequestStatus
from app.schemas.admin import (
    ContractorAdminCreate,
    ContractorAdminUpdate,
    ContractorMembershipPayload,
    RoleCreate,
    RoleUpdate,
    UserContractorsUpdate,
    UserCreate,
    UserRolesUpdate,
    UserUpdate,
)
from app.services.audit_service import write_audit

SYSTEM_ROLES = {
    "PLATFORM_ADMIN": "Platform Administrator",
    "SECURITY_ADMIN": "Security Administrator",
    "SECURITY_OPERATOR": "Security Operator",
    "CONTRACTOR_MANAGER": "Contractor Manager",
    "CONTRACTOR_USER": "Contractor User",
    "VIEWER": "Viewer",
}


def commit_or_conflict(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Record violates a database constraint") from exc


def snapshot(obj: Any, fields: Sequence[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in fields:
        value = getattr(obj, field)
        result[field] = str(value) if hasattr(value, "hex") else value
    return result


def ensure_seed_roles(db: Session) -> None:
    for code, name in SYSTEM_ROLES.items():
        role = db.scalar(select(Role).where(Role.code == code))
        if role is None:
            db.add(Role(code=code, name=name, description=f"System role: {name}", is_system=True, is_active=True))
    db.flush()


def get_or_404(db: Session, model: type[Any], item_id: UUID) -> Any:
    item = db.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    return item


def ensure_unique(db: Session, model: type[Any], field: str, value: Any, current_id: UUID | None = None) -> None:
    if value is None:
        return
    query = select(model).where(getattr(model, field) == value)
    if current_id is not None:
        query = query.where(model.id != current_id)
    if db.scalar(select(query.exists())):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{field} already exists")


def list_contractors(db: Session, search: str | None, is_active: bool | None, skip: int, limit: int) -> list[Contractor]:
    query = select(Contractor)
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(Contractor.name.ilike(pattern), Contractor.code.ilike(pattern), Contractor.email.ilike(pattern)))
    if is_active is not None:
        query = query.where(Contractor.is_active == is_active)
    return list(db.scalars(query.order_by(Contractor.name).offset(skip).limit(limit)).all())


def contractor_counts(db: Session, contractor_id: UUID) -> tuple[int, int]:
    users_count = db.scalar(select(func.count()).select_from(ContractorMembership).where(ContractorMembership.contractor_id == contractor_id, ContractorMembership.is_active.is_(True))) or 0
    responsibilities_count = db.scalar(select(func.count()).select_from(ContractorResponsibility).where(ContractorResponsibility.contractor_id == contractor_id)) or 0
    return users_count, responsibilities_count


def create_contractor(db: Session, payload: ContractorAdminCreate) -> Contractor:
    values = payload.model_dump()
    ensure_unique(db, Contractor, "code", values["code"])
    item = Contractor(**values)
    db.add(item)
    db.flush()
    write_audit(db, "CONTRACTOR_CREATED", "Contractor", item.id, new_data=values)
    commit_or_conflict(db)
    db.refresh(item)
    return item


def update_contractor(db: Session, item_id: UUID, payload: ContractorAdminUpdate) -> Contractor:
    item = get_or_404(db, Contractor, item_id)
    old = snapshot(item, ("name", "code", "email", "phone", "is_active"))
    values = payload.model_dump(exclude_unset=True)
    ensure_unique(db, Contractor, "code", values.get("code"), current_id=item_id)
    for field, value in values.items():
        setattr(item, field, value)
    write_audit(db, "CONTRACTOR_UPDATED", "Contractor", item.id, old_data=old, new_data=values)
    commit_or_conflict(db)
    db.refresh(item)
    return item


def set_contractor_active(db: Session, item_id: UUID, is_active: bool) -> Contractor:
    item = get_or_404(db, Contractor, item_id)
    old = {"is_active": item.is_active}
    item.is_active = is_active
    write_audit(db, "CONTRACTOR_DEACTIVATED" if not is_active else "CONTRACTOR_UPDATED", "Contractor", item.id, old_data=old, new_data={"is_active": is_active})
    commit_or_conflict(db)
    db.refresh(item)
    return item


def list_users(
    db: Session,
    search: str | None,
    user_type: UserType | None,
    role_id: UUID | None,
    contractor_id: UUID | None,
    is_active: bool | None,
    is_locked: bool | None,
    skip: int,
    limit: int,
) -> list[User]:
    query = select(User).options(selectinload(User.roles).selectinload(UserRole.role), selectinload(User.contractor_memberships))
    if role_id is not None:
        query = query.join(UserRole).where(UserRole.role_id == role_id)
    if contractor_id is not None:
        query = query.join(ContractorMembership).where(ContractorMembership.contractor_id == contractor_id)
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(User.username.ilike(pattern), User.display_name.ilike(pattern), User.email.ilike(pattern)))
    if user_type is not None:
        query = query.where(User.user_type == user_type)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if is_locked is not None:
        query = query.where(User.is_locked == is_locked)
    return list(db.scalars(query.order_by(User.username).offset(skip).limit(limit)).unique().all())


def validate_user_payload(db: Session, payload: UserCreate | UserUpdate, current_id: UUID | None = None) -> None:
    values = payload.model_dump(exclude_unset=True)
    ensure_unique(db, User, "username", values.get("username"), current_id=current_id)
    ensure_unique(db, User, "email", values.get("email"), current_id=current_id)


def replace_roles(db: Session, user: User, role_ids: list[UUID]) -> None:
    roles = list(db.scalars(select(Role).where(Role.id.in_(role_ids))).all()) if role_ids else []
    if len(roles) != len(set(role_ids)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more roles not found")
    db.execute(delete(UserRole).where(UserRole.user_id == user.id))
    db.flush()
    db.add_all(UserRole(user_id=user.id, role_id=role.id) for role in roles)
    db.expire(user, ["roles"])


def replace_memberships(db: Session, user: User, memberships: list[ContractorMembershipPayload]) -> None:
    contractor_ids = [item.contractor_id for item in memberships]
    contractors = list(db.scalars(select(Contractor).where(Contractor.id.in_(contractor_ids))).all()) if contractor_ids else []
    if len(contractors) != len(set(contractor_ids)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more contractors not found")
    if user.user_type == UserType.CONTRACTOR and not memberships:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Contractor user must have at least one contractor membership")
    db.execute(delete(ContractorMembership).where(ContractorMembership.user_id == user.id))
    db.flush()
    db.add_all(
        ContractorMembership(user_id=user.id, contractor_id=item.contractor_id, is_primary=item.is_primary, is_active=item.is_active)
        for item in memberships
    )
    db.expire(user, ["contractor_memberships"])


def create_user(db: Session, payload: UserCreate) -> User:
    validate_user_payload(db, payload)
    if payload.user_type == UserType.CONTRACTOR and not payload.contractor_memberships:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Contractor user must have at least one contractor membership")
    user = User(
        username=payload.username,
        email=payload.email,
        display_name=payload.display_name,
        user_type=payload.user_type,
        auth_source=payload.auth_source,
        is_active=payload.is_active,
        is_locked=payload.is_locked,
    )
    db.add(user)
    db.flush()
    replace_roles(db, user, payload.role_ids)
    replace_memberships(db, user, payload.contractor_memberships)
    write_audit(db, "USER_CREATED", "User", user.id, new_data=payload.model_dump(mode="json"))
    commit_or_conflict(db)
    return get_or_404(db, User, user.id)


def update_user(db: Session, user_id: UUID, payload: UserUpdate) -> User:
    user = get_or_404(db, User, user_id)
    old = snapshot(user, ("username", "email", "display_name", "user_type", "auth_source", "is_active", "is_locked"))
    validate_user_payload(db, payload, current_id=user_id)
    values = payload.model_dump(exclude_unset=True)
    for field, value in values.items():
        setattr(user, field, value)
    if user.user_type == UserType.CONTRACTOR and not user.contractor_memberships:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Contractor user must have at least one contractor membership")
    write_audit(db, "USER_UPDATED", "User", user.id, old_data=old, new_data=values)
    commit_or_conflict(db)
    return get_or_404(db, User, user.id)


def set_user_active(db: Session, user_id: UUID, is_active: bool) -> User:
    user = get_or_404(db, User, user_id)
    old = {"is_active": user.is_active}
    user.is_active = is_active
    write_audit(db, "USER_DEACTIVATED" if not is_active else "USER_UPDATED", "User", user.id, old_data=old, new_data={"is_active": is_active})
    commit_or_conflict(db)
    return get_or_404(db, User, user.id)


def set_user_roles(db: Session, user_id: UUID, payload: UserRolesUpdate) -> User:
    user = get_or_404(db, User, user_id)
    old = {"role_ids": [str(item.role_id) for item in user.roles]}
    replace_roles(db, user, payload.role_ids)
    write_audit(db, "USER_ROLE_CHANGED", "User", user.id, old_data=old, new_data=payload.model_dump(mode="json"))
    commit_or_conflict(db)
    return get_or_404(db, User, user.id)


def set_user_contractors(db: Session, user_id: UUID, payload: UserContractorsUpdate) -> User:
    user = get_or_404(db, User, user_id)
    replace_memberships(db, user, payload.contractor_memberships)
    write_audit(db, "USER_UPDATED", "User", user.id, new_data=payload.model_dump(mode="json"))
    commit_or_conflict(db)
    return get_or_404(db, User, user.id)


def list_roles(db: Session, search: str | None, is_active: bool | None, skip: int, limit: int) -> list[Role]:
    ensure_seed_roles(db)
    query = select(Role).options(selectinload(Role.users))
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(Role.code.ilike(pattern), Role.name.ilike(pattern)))
    if is_active is not None:
        query = query.where(Role.is_active == is_active)
    return list(db.scalars(query.order_by(Role.code).offset(skip).limit(limit)).unique().all())


def create_role(db: Session, payload: RoleCreate) -> Role:
    ensure_unique(db, Role, "code", payload.code)
    role = Role(**payload.model_dump(), is_system=False)
    db.add(role)
    write_audit(db, "USER_ROLE_CHANGED", "Role", role.id, new_data=payload.model_dump())
    commit_or_conflict(db)
    db.refresh(role)
    return role


def update_role(db: Session, role_id: UUID, payload: RoleUpdate) -> Role:
    role = get_or_404(db, Role, role_id)
    old = snapshot(role, ("name", "description", "is_active"))
    values = payload.model_dump(exclude_unset=True)
    if role.is_system and "is_active" in values and values["is_active"] is False:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="System role cannot be deactivated")
    for field, value in values.items():
        setattr(role, field, value)
    write_audit(db, "USER_ROLE_CHANGED", "Role", role.id, old_data=old, new_data=values)
    commit_or_conflict(db)
    db.refresh(role)
    return role


def deactivate_role(db: Session, role_id: UUID) -> Role:
    role = get_or_404(db, Role, role_id)
    if role.is_system:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="System role cannot be deactivated")
    role.is_active = False
    write_audit(db, "USER_ROLE_CHANGED", "Role", role.id, new_data={"is_active": False})
    commit_or_conflict(db)
    db.refresh(role)
    return role


def dashboard_counts(db: Session) -> dict[str, int]:
    active_statuses = {RequestStatus.NEW, RequestStatus.PARTIALLY_ASSIGNED, RequestStatus.ASSIGNED, RequestStatus.IN_PROGRESS}
    return {
        "contractors_total": db.scalar(select(func.count()).select_from(Contractor)) or 0,
        "contractors_active": db.scalar(select(func.count()).select_from(Contractor).where(Contractor.is_active.is_(True))) or 0,
        "users_total": db.scalar(select(func.count()).select_from(User)) or 0,
        "users_active": db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0,
        "cities_total": db.scalar(select(func.count()).select_from(City)) or 0,
        "facilities_total": db.scalar(select(func.count()).select_from(Facility)) or 0,
        "premises_total": db.scalar(select(func.count()).select_from(Premise)) or 0,
        "responsibilities_total": db.scalar(select(func.count()).select_from(ContractorResponsibility)) or 0,
        "requests_active": db.scalar(select(func.count()).select_from(ContractorRequest).where(ContractorRequest.status.in_(active_statuses))) or 0,
        "work_types_total": db.scalar(select(func.count()).select_from(WorkType)) or 0,
    }
