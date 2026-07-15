from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.requests import ContractorRequest, RequestAssignment, RequestHistory, RequestStatus, RequestWorkType
from app.schemas.requests import (
    ContractorRequestCreate,
    ContractorRequestResponse,
    ContractorRequestUpdate,
    RequestHistoryItem,
    RequestStatusUpdate,
)
from app.services.request_service import (
    change_request_status,
    create_contractor_request,
    publish_contractor_request,
    unassigned_work_type_ids,
    update_contractor_request,
)

router = APIRouter(prefix="/requests", tags=["contractor requests"])


def serialize_request(
    request: ContractorRequest,
    unassigned_work_type_ids: Sequence[UUID] | None = None,
) -> ContractorRequestResponse:
    return ContractorRequestResponse(
        id=request.id,
        request_number=request.request_number,
        city_id=request.city_id,
        facility_id=request.facility_id,
        premise_id=request.premise_id,
        title=request.title,
        description=request.description,
        contact_name=request.contact_name,
        contact_email=request.contact_email,
        contact_phone=request.contact_phone,
        priority=request.priority,
        desired_completion_date=request.desired_completion_date,
        completed_at=request.completed_at,
        closed_at=request.closed_at,
        status=request.status,
        work_type_ids=[item.work_type_id for item in request.work_types],
        assignments=request.assignments,
        unassigned_work_type_ids=list(unassigned_work_type_ids or unassigned_work_type_ids_fn(request)),
        created_at=request.created_at,
        updated_at=request.updated_at,
    )


def serialize_history(history: RequestHistory) -> RequestHistoryItem:
    return RequestHistoryItem(
        id=history.id,
        event_type=history.event_type,
        old_status=history.old_status,
        new_status=history.new_status,
        changed_fields=history.changed_fields,
        comment=history.comment,
        created_at=history.created_at,
        actor_type=history.actor_type,
        actor_id=history.actor_id,
    )


def unassigned_work_type_ids_fn(request: ContractorRequest) -> list[UUID]:
    return unassigned_work_type_ids(request)


def get_request_or_404(db: Session, request_id: UUID) -> ContractorRequest:
    request = db.scalar(
        select(ContractorRequest)
        .where(ContractorRequest.id == request_id)
        .options(
            selectinload(ContractorRequest.work_types),
            selectinload(ContractorRequest.assignments),
            selectinload(ContractorRequest.history),
        )
    )
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return request


@router.post(
    "",
    response_model=ContractorRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create contractor request",
)
def create_request(payload: ContractorRequestCreate, db: Session = Depends(get_db)) -> ContractorRequestResponse:
    request, unassigned = create_contractor_request(db, payload)
    return serialize_request(get_request_or_404(db, request.id), unassigned)


def apply_request_filters(
    statement: Select[tuple[ContractorRequest]],
    search: str | None,
    request_status: RequestStatus | None,
    priority: str | None,
    city_id: UUID | None,
    facility_id: UUID | None,
    work_type_id: UUID | None,
    contractor_id: UUID | None,
    created_from: datetime | None,
    created_to: datetime | None,
    due_from: datetime | None,
    due_to: datetime | None,
) -> Select[tuple[ContractorRequest]]:
    if search:
        like = f"%{search}%"
        statement = statement.where(
            or_(
                ContractorRequest.request_number.ilike(like),
                ContractorRequest.title.ilike(like),
                ContractorRequest.description.ilike(like),
            )
        )
    if request_status:
        statement = statement.where(ContractorRequest.status == request_status)
    if priority:
        statement = statement.where(ContractorRequest.priority == priority)
    if city_id:
        statement = statement.where(ContractorRequest.city_id == city_id)
    if facility_id:
        statement = statement.where(ContractorRequest.facility_id == facility_id)
    if work_type_id:
        statement = statement.join(RequestWorkType).where(RequestWorkType.work_type_id == work_type_id)
    if contractor_id:
        statement = statement.join(RequestAssignment).where(RequestAssignment.contractor_id == contractor_id)
    if created_from:
        statement = statement.where(ContractorRequest.created_at >= created_from)
    if created_to:
        statement = statement.where(ContractorRequest.created_at <= created_to)
    if due_from:
        statement = statement.where(ContractorRequest.desired_completion_date >= due_from)
    if due_to:
        statement = statement.where(ContractorRequest.desired_completion_date <= due_to)
    return statement


@router.get("", response_model=list[ContractorRequestResponse], summary="List contractor requests")
def list_requests(
    db: Session = Depends(get_db),
    search: str | None = None,
    status_filter: RequestStatus | None = Query(default=None, alias="status"),
    priority: str | None = None,
    city_id: UUID | None = None,
    facility_id: UUID | None = None,
    work_type_id: UUID | None = None,
    contractor_id: UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    due_from: datetime | None = None,
    due_to: datetime | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
) -> list[ContractorRequestResponse]:
    sort_columns = {
        "created_at": ContractorRequest.created_at,
        "updated_at": ContractorRequest.updated_at,
        "number": ContractorRequest.request_number,
        "status": ContractorRequest.status,
        "priority": ContractorRequest.priority,
        "desired_completion_date": ContractorRequest.desired_completion_date,
    }
    if sort_by not in sort_columns:
        raise HTTPException(status_code=422, detail="Invalid sort_by")

    statement = select(ContractorRequest).options(selectinload(ContractorRequest.work_types), selectinload(ContractorRequest.assignments))
    statement = apply_request_filters(
        statement,
        search,
        status_filter,
        priority,
        city_id,
        facility_id,
        work_type_id,
        contractor_id,
        created_from,
        created_to,
        due_from,
        due_to,
    )
    sort_column = sort_columns[sort_by]
    statement = statement.order_by(sort_column.asc() if sort_order == "asc" else sort_column.desc()).offset(skip).limit(limit)
    requests = db.scalars(statement).unique().all()
    return [serialize_request(request) for request in requests]


@router.get("/{request_id}", response_model=ContractorRequestResponse, summary="Get contractor request by id")
def get_request(request_id: UUID, db: Session = Depends(get_db)) -> ContractorRequestResponse:
    return serialize_request(get_request_or_404(db, request_id))


@router.patch("/{request_id}", response_model=ContractorRequestResponse, summary="Update contractor request")
def update_request(
    request_id: UUID,
    payload: ContractorRequestUpdate,
    db: Session = Depends(get_db),
) -> ContractorRequestResponse:
    request = get_request_or_404(db, request_id)
    request, unassigned = update_contractor_request(db, request, payload)
    return serialize_request(get_request_or_404(db, request.id), unassigned)


@router.post("/{request_id}/publish", response_model=ContractorRequestResponse, summary="Publish contractor request")
def publish_request(request_id: UUID, db: Session = Depends(get_db)) -> ContractorRequestResponse:
    request = get_request_or_404(db, request_id)
    request, unassigned = publish_contractor_request(db, request)
    return serialize_request(get_request_or_404(db, request.id), unassigned)


@router.post("/{request_id}/status", response_model=ContractorRequestResponse, summary="Change contractor request status")
def update_request_status(
    request_id: UUID,
    payload: RequestStatusUpdate,
    db: Session = Depends(get_db),
) -> ContractorRequestResponse:
    request = get_request_or_404(db, request_id)
    change_request_status(db, request, payload.status, comment=payload.comment)
    return serialize_request(get_request_or_404(db, request_id))


@router.get("/{request_id}/history", response_model=list[RequestHistoryItem], summary="Get contractor request history")
def get_request_history(request_id: UUID, db: Session = Depends(get_db)) -> list[RequestHistoryItem]:
    get_request_or_404(db, request_id)
    history = db.scalars(select(RequestHistory).where(RequestHistory.request_id == request_id).order_by(RequestHistory.created_at.asc())).all()
    return [serialize_history(item) for item in history]
