from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_contractor_id
from app.db.session import get_db
from app.models.reference_data import Contractor
from app.models.requests import (
    AssignmentStatus,
    ContractorRequest,
    RequestAssignment,
    RequestHistory,
    RequestHistoryActorType,
    RequestHistoryEventType,
)
from app.schemas.requests import (
    AssignmentStatusUpdate,
    ContractorAssignmentResponse,
    ContractorRequestListResponse,
    RequestHistoryItem,
)
from app.services.request_service import change_assignment_status

router = APIRouter(prefix="/contractor", tags=["contractor portal"])

CONTRACTOR_VISIBLE_EVENTS = {
    RequestHistoryEventType.PUBLISHED,
    RequestHistoryEventType.ASSIGNMENT_CREATED,
    RequestHistoryEventType.ASSIGNMENT_ACCEPTED,
    RequestHistoryEventType.ASSIGNMENT_STATUS_CHANGED,
    RequestHistoryEventType.STATUS_CHANGED,
    RequestHistoryEventType.REOPENED,
    RequestHistoryEventType.CLOSED,
    RequestHistoryEventType.CANCELLED,
}


def serialize_contractor_request(
    request: ContractorRequest,
    contractor_id: UUID,
) -> ContractorRequestListResponse:
    own_assignments = [
        ContractorAssignmentResponse.model_validate(assignment)
        for assignment in request.assignments
        if assignment.contractor_id == contractor_id
    ]
    return ContractorRequestListResponse(
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
        work_type_ids=[assignment.work_type_id for assignment in request.assignments if assignment.contractor_id == contractor_id],
        assignments=own_assignments,
        created_at=request.created_at,
        updated_at=request.updated_at,
    )


def ensure_contractor_exists(db: Session, contractor_id: UUID) -> None:
    if db.get(Contractor, contractor_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contractor not found")


def get_owned_request(db: Session, request_id: UUID, contractor_id: UUID) -> ContractorRequest:
    request = db.scalar(
        select(ContractorRequest)
        .join(RequestAssignment)
        .where(ContractorRequest.id == request_id, RequestAssignment.contractor_id == contractor_id)
        .options(selectinload(ContractorRequest.assignments), selectinload(ContractorRequest.work_types))
    )
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return request


@router.get(
    "/requests",
    response_model=list[ContractorRequestListResponse],
    summary="List contractor-visible requests",
)
def list_contractor_requests(
    db: Session = Depends(get_db),
    contractor_id: UUID = Depends(get_current_contractor_id),
) -> list[ContractorRequestListResponse]:
    ensure_contractor_exists(db, contractor_id)
    requests = db.scalars(
        select(ContractorRequest)
        .join(RequestAssignment)
        .where(RequestAssignment.contractor_id == contractor_id)
        .options(selectinload(ContractorRequest.assignments), selectinload(ContractorRequest.work_types))
        .order_by(ContractorRequest.created_at.desc())
    ).unique().all()
    return [serialize_contractor_request(request, contractor_id) for request in requests]


@router.get("/requests/{request_id}", response_model=ContractorRequestListResponse, summary="Get contractor-visible request")
def get_contractor_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    contractor_id: UUID = Depends(get_current_contractor_id),
) -> ContractorRequestListResponse:
    ensure_contractor_exists(db, contractor_id)
    return serialize_contractor_request(get_owned_request(db, request_id, contractor_id), contractor_id)


@router.post("/requests/{request_id}/accept", response_model=ContractorRequestListResponse, summary="Accept request assignments")
def accept_contractor_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    contractor_id: UUID = Depends(get_current_contractor_id),
) -> ContractorRequestListResponse:
    ensure_contractor_exists(db, contractor_id)
    request = get_owned_request(db, request_id, contractor_id)
    for assignment in request.assignments:
        if assignment.contractor_id == contractor_id and assignment.status == AssignmentStatus.ASSIGNED:
            change_assignment_status(
                db,
                assignment,
                AssignmentStatus.ACCEPTED,
                actor_type=RequestHistoryActorType.CONTRACTOR_USER,
                actor_id=contractor_id,
                commit=False,
            )
    db.commit()
    return serialize_contractor_request(get_owned_request(db, request_id, contractor_id), contractor_id)


@router.post(
    "/assignments/{assignment_id}/status",
    response_model=ContractorAssignmentResponse,
    summary="Update own assignment status",
)
def update_assignment_status(
    assignment_id: UUID,
    payload: AssignmentStatusUpdate,
    db: Session = Depends(get_db),
    contractor_id: UUID = Depends(get_current_contractor_id),
) -> ContractorAssignmentResponse:
    ensure_contractor_exists(db, contractor_id)
    assignment = db.scalar(
        select(RequestAssignment)
        .where(
            RequestAssignment.id == assignment_id,
            RequestAssignment.contractor_id == contractor_id,
        )
        .options(selectinload(RequestAssignment.request).selectinload(ContractorRequest.assignments), selectinload(RequestAssignment.request).selectinload(ContractorRequest.work_types))
    )
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    change_assignment_status(
        db,
        assignment,
        payload.status,
        actor_type=RequestHistoryActorType.CONTRACTOR_USER,
        actor_id=contractor_id,
        comment=payload.comment,
    )
    return ContractorAssignmentResponse.model_validate(assignment)


@router.get(
    "/requests/{request_id}/history",
    response_model=list[RequestHistoryItem],
    summary="Get contractor-visible request history",
)
def get_contractor_request_history(
    request_id: UUID,
    db: Session = Depends(get_db),
    contractor_id: UUID = Depends(get_current_contractor_id),
) -> list[RequestHistoryItem]:
    get_owned_request(db, request_id, contractor_id)
    history = db.scalars(select(RequestHistory).where(RequestHistory.request_id == request_id).order_by(RequestHistory.created_at.asc())).all()
    visible: list[RequestHistoryItem] = []
    for item in history:
        if item.event_type not in CONTRACTOR_VISIBLE_EVENTS:
            continue
        changed_fields = None
        if item.changed_fields and "assignment_status" in item.changed_fields:
            changed_fields = {"assignment_status": item.changed_fields["assignment_status"]}
        visible.append(
            RequestHistoryItem(
                id=item.id,
                event_type=item.event_type,
                old_status=item.old_status,
                new_status=item.new_status,
                changed_fields=changed_fields,
                comment=item.comment,
                created_at=item.created_at,
                actor_type=RequestHistoryActorType.CONTRACTOR_USER if item.actor_type == RequestHistoryActorType.CONTRACTOR_USER else RequestHistoryActorType.SYSTEM,
                actor_id=item.actor_id if item.actor_type == RequestHistoryActorType.CONTRACTOR_USER else None,
            )
        )
    return visible
