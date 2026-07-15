from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_contractor_id
from app.db.session import get_db
from app.models.reference_data import Contractor
from app.models.requests import AssignmentStatus, ContractorRequest, RequestAssignment, utc_now
from app.schemas.requests import (
    AssignmentStatusUpdate,
    ContractorAssignmentResponse,
    ContractorRequestListResponse,
    RequestHistoryItem,
)

router = APIRouter(prefix="/contractor", tags=["contractor portal"])


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
        city_id=request.city_id,
        facility_id=request.facility_id,
        premise_id=request.premise_id,
        title=request.title,
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
        .options(selectinload(ContractorRequest.assignments))
    )
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return request


@router.get(
    "/requests",
    response_model=list[ContractorRequestListResponse],
    summary="List contractor-visible requests",
    description="Returns only requests assigned to the current contractor dependency context.",
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
        .options(selectinload(ContractorRequest.assignments))
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
    now = utc_now()
    for assignment in request.assignments:
        if assignment.contractor_id == contractor_id and assignment.status == AssignmentStatus.ASSIGNED:
            assignment.status = AssignmentStatus.ACCEPTED
            assignment.accepted_at = now
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
        select(RequestAssignment).where(
            RequestAssignment.id == assignment_id,
            RequestAssignment.contractor_id == contractor_id,
        )
    )
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    assignment.status = payload.status
    if payload.status == AssignmentStatus.ACCEPTED and assignment.accepted_at is None:
        assignment.accepted_at = utc_now()
    if payload.status == AssignmentStatus.COMPLETED:
        assignment.completed_at = utc_now()
    db.commit()
    db.refresh(assignment)
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
    request = get_owned_request(db, request_id, contractor_id)
    return [
        RequestHistoryItem(event=f"assignment:{assignment.status}", created_at=assignment.updated_at)
        for assignment in request.assignments
        if assignment.contractor_id == contractor_id
    ]
