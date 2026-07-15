from collections.abc import Sequence
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reference_data import City, ContractorResponsibility, Facility, Premise, WorkType
from app.models.requests import ContractorRequest, RequestAssignment, RequestStatus, RequestWorkType
from app.schemas.requests import ContractorRequestCreate, ContractorRequestUpdate


def validate_request_scope(
    db: Session,
    city_id: UUID,
    facility_id: UUID,
    premise_id: UUID | None,
    work_type_ids: list[UUID],
) -> tuple[Facility, Premise | None, list[WorkType]]:
    if db.get(City, city_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="City not found")

    facility = db.get(Facility, facility_id)
    if facility is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found")
    if facility.city_id != city_id:
        raise HTTPException(status_code=422, detail="Facility does not belong to city")

    work_types = list(db.scalars(select(WorkType).where(WorkType.id.in_(work_type_ids), WorkType.is_active.is_(True))).all())
    if len(work_types) != len(work_type_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more work types not found")

    premise = None
    requires_premise = any(work_type.requires_premise for work_type in work_types)
    if requires_premise and premise_id is None:
        raise HTTPException(status_code=422, detail="premise_id is required")
    if premise_id is not None:
        premise = db.get(Premise, premise_id)
        if premise is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Premise not found")
        if premise.facility_id != facility_id:
            raise HTTPException(status_code=422, detail="Premise does not belong to facility")

    return facility, premise, work_types


def find_contractor_for_work_type(
    db: Session,
    city_id: UUID,
    facility_id: UUID,
    work_type_id: UUID,
) -> ContractorResponsibility | None:
    filters = (
        (ContractorResponsibility.facility_id == facility_id,),
        (ContractorResponsibility.city_id == city_id, ContractorResponsibility.facility_id.is_(None)),
        (ContractorResponsibility.city_id.is_(None), ContractorResponsibility.facility_id.is_(None)),
    )
    for scope_filters in filters:
        responsibility = db.scalar(
            select(ContractorResponsibility)
            .where(
                ContractorResponsibility.is_active.is_(True),
                ContractorResponsibility.work_type_id == work_type_id,
                *scope_filters,
            )
            .order_by(ContractorResponsibility.priority.asc())
            .limit(1)
        )
        if responsibility is not None:
            return responsibility
    return None


def apply_premise_contacts(request: ContractorRequest, premise: Premise | None) -> None:
    if premise is None:
        return
    request.contact_name = request.contact_name or premise.owner_name
    request.contact_email = request.contact_email or premise.owner_email
    request.contact_phone = request.contact_phone or premise.owner_phone


def rebuild_work_types_and_assignments(
    db: Session,
    request: ContractorRequest,
    work_type_ids: list[UUID],
) -> list[UUID]:
    request.work_types.clear()
    request.assignments.clear()
    db.flush()

    unassigned_work_type_ids: list[UUID] = []
    for work_type_id in work_type_ids:
        request.work_types.append(RequestWorkType(work_type_id=work_type_id))
        responsibility = find_contractor_for_work_type(db, request.city_id, request.facility_id, work_type_id)
        if responsibility is None:
            unassigned_work_type_ids.append(work_type_id)
            continue
        request.assignments.append(
            RequestAssignment(
                contractor_id=responsibility.contractor_id,
                work_type_id=work_type_id,
            )
        )

    request.status = RequestStatus.NEW if unassigned_work_type_ids else RequestStatus.ASSIGNED
    return unassigned_work_type_ids


def create_contractor_request(
    db: Session,
    payload: ContractorRequestCreate,
    request_number: str | None = None,
    commit: bool = True,
) -> tuple[ContractorRequest, Sequence[UUID]]:
    _, premise, _ = validate_request_scope(db, payload.city_id, payload.facility_id, payload.premise_id, payload.work_type_ids)

    request = ContractorRequest(
        request_number=request_number,
        city_id=payload.city_id,
        facility_id=payload.facility_id,
        premise_id=payload.premise_id,
        title=payload.title,
        description=payload.description,
        contact_name=payload.contact_name,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
    )
    apply_premise_contacts(request, premise)
    db.add(request)
    db.flush()

    if request.request_number is None:
        request.request_number = f"CR-{request.created_at:%Y%m%d}-{str(request.id)[:8].upper()}"

    unassigned = rebuild_work_types_and_assignments(db, request, payload.work_type_ids)
    if commit:
        db.commit()
        db.refresh(request)
    return request, unassigned


def update_contractor_request(
    db: Session,
    request: ContractorRequest,
    payload: ContractorRequestUpdate,
    commit: bool = True,
) -> tuple[ContractorRequest, Sequence[UUID]]:
    values = payload.model_dump(exclude_unset=True)
    city_id = values.get("city_id", request.city_id)
    facility_id = values.get("facility_id", request.facility_id)
    premise_id = values.get("premise_id", request.premise_id)
    work_type_ids = values.get("work_type_ids", [item.work_type_id for item in request.work_types])
    _, premise, _ = validate_request_scope(db, city_id, facility_id, premise_id, work_type_ids)

    for field in ("city_id", "facility_id", "premise_id", "title", "description", "contact_name", "contact_email", "contact_phone"):
        if field in values:
            setattr(request, field, values[field])
    apply_premise_contacts(request, premise)
    unassigned = rebuild_work_types_and_assignments(db, request, work_type_ids)
    if commit:
        db.commit()
        db.refresh(request)
    return request, unassigned
