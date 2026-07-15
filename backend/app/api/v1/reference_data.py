from collections.abc import Sequence
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import Select, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.reference_data import (
    City,
    Contractor,
    ContractorResponsibility,
    Facility,
    Premise,
    WorkType,
)
from app.schemas.reference_data import (
    CityCreate,
    CityResponse,
    CityUpdate,
    ContractorCreate,
    ContractorResponsibilityCreate,
    ContractorResponsibilityResponse,
    ContractorResponsibilityUpdate,
    ContractorResponse,
    ContractorUpdate,
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

router = APIRouter()


def get_object_or_404(db: Session, model: type[Any], item_id: UUID) -> Any:
    item = db.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    return item


def ensure_exists(db: Session, model: type[Any], item_id: UUID | None, name: str) -> None:
    if item_id is not None and db.get(model, item_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{name} not found",
        )


def ensure_unique(
    db: Session,
    model: type[Any],
    values: dict[str, Any],
    unique_fields: Sequence[str],
    current_id: UUID | None = None,
) -> None:
    for field in unique_fields:
        value = values.get(field)
        if value is None:
            continue
        query = select(model).where(getattr(model, field) == value)
        if current_id is not None:
            query = query.where(model.id != current_id)
        if db.scalar(select(query.exists())):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{field} already exists",
            )


def commit_or_conflict(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Record violates a database constraint",
        ) from exc


def apply_common_filters(
    query: Select[tuple[Any]],
    model: type[Any],
    is_active: bool | None,
    search: str | None,
) -> Select[tuple[Any]]:
    if is_active is not None:
        query = query.where(model.is_active == is_active)
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(model.name.ilike(pattern), model.code.ilike(pattern)))
    return query


def list_records(
    db: Session,
    query: Select[tuple[Any]],
    skip: int,
    limit: int,
) -> Sequence[Any]:
    return db.scalars(query.order_by("name").offset(skip).limit(limit)).all()


def create_record(db: Session, model: type[Any], payload: Any) -> Any:
    values = payload.model_dump()
    ensure_unique(db, model, values, get_unique_fields(model))
    item = model(**values)
    db.add(item)
    commit_or_conflict(db)
    db.refresh(item)
    return item


def update_record(db: Session, model: type[Any], item_id: UUID, payload: Any) -> Any:
    item = get_object_or_404(db, model, item_id)
    values = payload.model_dump(exclude_unset=True)
    ensure_unique(db, model, values, get_unique_fields(model), current_id=item_id)
    for field, value in values.items():
        setattr(item, field, value)
    commit_or_conflict(db)
    db.refresh(item)
    return item


def delete_record(db: Session, model: type[Any], item_id: UUID) -> Response:
    item = get_object_or_404(db, model, item_id)
    db.delete(item)
    commit_or_conflict(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def has_references(db: Session, checks: Sequence[tuple[type[Any], Any, UUID]]) -> bool:
    for model, column, value in checks:
        exists_query = select(model).where(column == value).limit(1)
        if db.scalar(select(exists_query.exists())):
            return True
    return False


def get_unique_fields(model: type[Any]) -> tuple[str, ...]:
    if model is City:
        return ("name", "code")
    if model in (Facility, Contractor, WorkType):
        return ("code",)
    return ()


@router.get(
    "/cities",
    response_model=list[CityResponse],
    summary="List cities",
    description="Returns active or inactive company cities with pagination and name/code search.",
)
def list_cities(
    db: Session = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
) -> Sequence[City]:
    query = apply_common_filters(select(City), City, is_active, search)
    return list_records(db, query, skip, limit)


@router.post(
    "/cities",
    response_model=CityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create city",
)
def create_city(payload: CityCreate, db: Session = Depends(get_db)) -> City:
    return create_record(db, City, payload)


@router.get("/cities/{item_id}", response_model=CityResponse, summary="Get city by id")
def get_city(item_id: UUID, db: Session = Depends(get_db)) -> City:
    return get_object_or_404(db, City, item_id)


@router.patch("/cities/{item_id}", response_model=CityResponse, summary="Update city")
def update_city(item_id: UUID, payload: CityUpdate, db: Session = Depends(get_db)) -> City:
    return update_record(db, City, item_id, payload)


@router.delete("/cities/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete city")
def delete_city(item_id: UUID, db: Session = Depends(get_db)) -> Response:
    if has_references(db, [(Facility, Facility.city_id, item_id), (ContractorResponsibility, ContractorResponsibility.city_id, item_id)]):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="City is referenced by other records")
    return delete_record(db, City, item_id)


@router.get(
    "/facilities",
    response_model=list[FacilityResponse],
    summary="List facilities",
    description="Returns facilities with pagination, city filter, is_active filter and name/code search.",
)
def list_facilities(
    db: Session = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    city_id: UUID | None = Query(default=None),
) -> Sequence[Facility]:
    query = apply_common_filters(select(Facility), Facility, is_active, search)
    if city_id is not None:
        query = query.where(Facility.city_id == city_id)
    return list_records(db, query, skip, limit)


@router.post("/facilities", response_model=FacilityResponse, status_code=status.HTTP_201_CREATED, summary="Create facility")
def create_facility(payload: FacilityCreate, db: Session = Depends(get_db)) -> Facility:
    ensure_exists(db, City, payload.city_id, "City")
    return create_record(db, Facility, payload)


@router.get("/facilities/{item_id}", response_model=FacilityResponse, summary="Get facility by id")
def get_facility(item_id: UUID, db: Session = Depends(get_db)) -> Facility:
    return get_object_or_404(db, Facility, item_id)


@router.patch("/facilities/{item_id}", response_model=FacilityResponse, summary="Update facility")
def update_facility(item_id: UUID, payload: FacilityUpdate, db: Session = Depends(get_db)) -> Facility:
    if payload.city_id is not None:
        ensure_exists(db, City, payload.city_id, "City")
    return update_record(db, Facility, item_id, payload)


@router.delete("/facilities/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete facility")
def delete_facility(item_id: UUID, db: Session = Depends(get_db)) -> Response:
    if has_references(db, [(Premise, Premise.facility_id, item_id), (ContractorResponsibility, ContractorResponsibility.facility_id, item_id)]):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Facility is referenced by other records")
    return delete_record(db, Facility, item_id)


@router.get(
    "/premises",
    response_model=list[PremiseResponse],
    summary="List premises",
    description="Returns premises with pagination, facility filter and is_active filter.",
)
def list_premises(
    db: Session = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    facility_id: UUID | None = Query(default=None),
) -> Sequence[Premise]:
    query = select(Premise)
    if is_active is not None:
        query = query.where(Premise.is_active == is_active)
    if search:
        query = query.where(Premise.name.ilike(f"%{search}%"))
    if facility_id is not None:
        query = query.where(Premise.facility_id == facility_id)
    return list_records(db, query, skip, limit)


@router.post("/premises", response_model=PremiseResponse, status_code=status.HTTP_201_CREATED, summary="Create premise")
def create_premise(payload: PremiseCreate, db: Session = Depends(get_db)) -> Premise:
    ensure_exists(db, Facility, payload.facility_id, "Facility")
    return create_record(db, Premise, payload)


@router.get("/premises/{item_id}", response_model=PremiseResponse, summary="Get premise by id")
def get_premise(item_id: UUID, db: Session = Depends(get_db)) -> Premise:
    return get_object_or_404(db, Premise, item_id)


@router.patch("/premises/{item_id}", response_model=PremiseResponse, summary="Update premise")
def update_premise(item_id: UUID, payload: PremiseUpdate, db: Session = Depends(get_db)) -> Premise:
    if payload.facility_id is not None:
        ensure_exists(db, Facility, payload.facility_id, "Facility")
    return update_record(db, Premise, item_id, payload)


@router.delete("/premises/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete premise")
def delete_premise(item_id: UUID, db: Session = Depends(get_db)) -> Response:
    return delete_record(db, Premise, item_id)


@router.get(
    "/contractors",
    response_model=list[ContractorResponse],
    summary="List contractors",
    description="Returns contractors with pagination, is_active filter and name/code search.",
)
def list_contractors(
    db: Session = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
) -> Sequence[Contractor]:
    query = apply_common_filters(select(Contractor), Contractor, is_active, search)
    return list_records(db, query, skip, limit)


@router.post("/contractors", response_model=ContractorResponse, status_code=status.HTTP_201_CREATED, summary="Create contractor")
def create_contractor(payload: ContractorCreate, db: Session = Depends(get_db)) -> Contractor:
    return create_record(db, Contractor, payload)


@router.get("/contractors/{item_id}", response_model=ContractorResponse, summary="Get contractor by id")
def get_contractor(item_id: UUID, db: Session = Depends(get_db)) -> Contractor:
    return get_object_or_404(db, Contractor, item_id)


@router.patch("/contractors/{item_id}", response_model=ContractorResponse, summary="Update contractor")
def update_contractor(item_id: UUID, payload: ContractorUpdate, db: Session = Depends(get_db)) -> Contractor:
    return update_record(db, Contractor, item_id, payload)


@router.delete("/contractors/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete contractor")
def delete_contractor(item_id: UUID, db: Session = Depends(get_db)) -> Response:
    if has_references(db, [(ContractorResponsibility, ContractorResponsibility.contractor_id, item_id)]):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Contractor is referenced by other records")
    return delete_record(db, Contractor, item_id)


@router.get(
    "/work-types",
    response_model=list[WorkTypeResponse],
    summary="List work types",
    description="Returns work types with pagination, is_active filter and name/code search.",
)
def list_work_types(
    db: Session = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
) -> Sequence[WorkType]:
    query = apply_common_filters(select(WorkType), WorkType, is_active, search)
    return list_records(db, query, skip, limit)


@router.post("/work-types", response_model=WorkTypeResponse, status_code=status.HTTP_201_CREATED, summary="Create work type")
def create_work_type(payload: WorkTypeCreate, db: Session = Depends(get_db)) -> WorkType:
    return create_record(db, WorkType, payload)


@router.get("/work-types/{item_id}", response_model=WorkTypeResponse, summary="Get work type by id")
def get_work_type(item_id: UUID, db: Session = Depends(get_db)) -> WorkType:
    return get_object_or_404(db, WorkType, item_id)


@router.patch("/work-types/{item_id}", response_model=WorkTypeResponse, summary="Update work type")
def update_work_type(item_id: UUID, payload: WorkTypeUpdate, db: Session = Depends(get_db)) -> WorkType:
    return update_record(db, WorkType, item_id, payload)


@router.delete("/work-types/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete work type")
def delete_work_type(item_id: UUID, db: Session = Depends(get_db)) -> Response:
    if has_references(db, [(ContractorResponsibility, ContractorResponsibility.work_type_id, item_id)]):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Work type is referenced by other records")
    return delete_record(db, WorkType, item_id)


@router.get(
    "/contractor-responsibilities",
    response_model=list[ContractorResponsibilityResponse],
    summary="List contractor responsibilities",
    description="Returns contractor responsibility scopes with pagination and FK filters.",
)
def list_contractor_responsibilities(
    db: Session = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    is_active: bool | None = Query(default=None),
    contractor_id: UUID | None = Query(default=None),
    city_id: UUID | None = Query(default=None),
    facility_id: UUID | None = Query(default=None),
    work_type_id: UUID | None = Query(default=None),
) -> Sequence[ContractorResponsibility]:
    query = select(ContractorResponsibility)
    if is_active is not None:
        query = query.where(ContractorResponsibility.is_active == is_active)
    if contractor_id is not None:
        query = query.where(ContractorResponsibility.contractor_id == contractor_id)
    if city_id is not None:
        query = query.where(ContractorResponsibility.city_id == city_id)
    if facility_id is not None:
        query = query.where(ContractorResponsibility.facility_id == facility_id)
    if work_type_id is not None:
        query = query.where(ContractorResponsibility.work_type_id == work_type_id)
    return db.scalars(query.order_by(ContractorResponsibility.priority).offset(skip).limit(limit)).all()


@router.post(
    "/contractor-responsibilities",
    response_model=ContractorResponsibilityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create contractor responsibility",
)
def create_contractor_responsibility(
    payload: ContractorResponsibilityCreate,
    db: Session = Depends(get_db),
) -> ContractorResponsibility:
    ensure_responsibility_refs(db, payload.model_dump())
    return create_record(db, ContractorResponsibility, payload)


@router.get(
    "/contractor-responsibilities/{item_id}",
    response_model=ContractorResponsibilityResponse,
    summary="Get contractor responsibility by id",
)
def get_contractor_responsibility(item_id: UUID, db: Session = Depends(get_db)) -> ContractorResponsibility:
    return get_object_or_404(db, ContractorResponsibility, item_id)


@router.patch(
    "/contractor-responsibilities/{item_id}",
    response_model=ContractorResponsibilityResponse,
    summary="Update contractor responsibility",
)
def update_contractor_responsibility(
    item_id: UUID,
    payload: ContractorResponsibilityUpdate,
    db: Session = Depends(get_db),
) -> ContractorResponsibility:
    ensure_responsibility_refs(db, payload.model_dump(exclude_unset=True))
    return update_record(db, ContractorResponsibility, item_id, payload)


@router.delete(
    "/contractor-responsibilities/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete contractor responsibility",
)
def delete_contractor_responsibility(item_id: UUID, db: Session = Depends(get_db)) -> Response:
    return delete_record(db, ContractorResponsibility, item_id)


def ensure_responsibility_refs(db: Session, values: dict[str, Any]) -> None:
    ensure_exists(db, Contractor, values.get("contractor_id"), "Contractor")
    ensure_exists(db, City, values.get("city_id"), "City")
    ensure_exists(db, Facility, values.get("facility_id"), "Facility")
    ensure_exists(db, WorkType, values.get("work_type_id"), "Work type")
