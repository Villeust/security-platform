from collections.abc import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.requests import ContractorRequest
from app.schemas.requests import ContractorRequestCreate, ContractorRequestResponse, ContractorRequestUpdate
from app.services.request_service import create_contractor_request, update_contractor_request

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
        status=request.status,
        work_type_ids=[item.work_type_id for item in request.work_types],
        assignments=request.assignments,
        unassigned_work_type_ids=list(unassigned_work_type_ids or []),
        created_at=request.created_at,
        updated_at=request.updated_at,
    )


def get_request_or_404(db: Session, request_id: UUID) -> ContractorRequest:
    request = db.scalar(
        select(ContractorRequest)
        .where(ContractorRequest.id == request_id)
        .options(
            selectinload(ContractorRequest.work_types),
            selectinload(ContractorRequest.assignments),
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
    description="Creates a contractor request with one or more work types and resolves contractor assignments per work type.",
)
def create_request(payload: ContractorRequestCreate, db: Session = Depends(get_db)) -> ContractorRequestResponse:
    request, unassigned = create_contractor_request(db, payload)
    return serialize_request(get_request_or_404(db, request.id), unassigned)


@router.get(
    "",
    response_model=list[ContractorRequestResponse],
    summary="List contractor requests",
    description="Returns contractor requests with pagination.",
)
def list_requests(
    db: Session = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> list[ContractorRequestResponse]:
    requests = db.scalars(
        select(ContractorRequest)
        .options(selectinload(ContractorRequest.work_types), selectinload(ContractorRequest.assignments))
        .order_by(ContractorRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()
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
