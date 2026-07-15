from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_contractor_id
from app.db.session import get_db
from app.models.reference_data import Contractor
from app.models.requests import (
    AssignmentStatus,
    ContractorRequest,
    RequestAssignment,
    RequestAttachmentCategory,
    RequestHistory,
    RequestHistoryActorType,
    RequestHistoryEventType,
    RequestVisibility,
)
from app.schemas.collaboration import RequestAttachmentResponse, RequestCommentCreate, RequestCommentResponse, RequestCommentUpdate
from app.schemas.requests import (
    AssignmentStatusUpdate,
    ContractorAssignmentResponse,
    ContractorRequestListResponse,
    RequestHistoryItem,
)
from app.services.request_service import change_assignment_status
from app.services.attachment_service import (
    attachment_file_path,
    create_attachment,
    delete_attachment,
    ensure_contractor_can_access_attachment,
    get_attachment_or_404,
    list_contractor_attachments,
)
from app.services.comment_service import (
    create_contractor_comment,
    delete_comment,
    get_comment_or_404,
    list_contractor_comments,
    serialize_comment_body,
    update_comment,
)

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
    RequestHistoryEventType.COMMENT_ADDED,
    RequestHistoryEventType.COMMENT_UPDATED,
    RequestHistoryEventType.COMMENT_DELETED,
    RequestHistoryEventType.ATTACHMENT_ADDED,
    RequestHistoryEventType.ATTACHMENT_DELETED,
    RequestHistoryEventType.WORK_RESULT_ADDED,
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


def serialize_contractor_comment(comment) -> RequestCommentResponse:
    return RequestCommentResponse(
        id=comment.id,
        request_id=comment.request_id,
        author_type=comment.author_type if comment.author_type == RequestHistoryActorType.CONTRACTOR_USER else RequestHistoryActorType.SYSTEM,
        author_id=comment.author_id if comment.author_type == RequestHistoryActorType.CONTRACTOR_USER else None,
        contractor_id=comment.contractor_id if comment.author_type == RequestHistoryActorType.CONTRACTOR_USER else None,
        visibility=comment.visibility,
        body=serialize_comment_body(comment),
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        is_edited=comment.is_edited,
        is_deleted=comment.is_deleted,
    )


def serialize_contractor_attachment(attachment) -> RequestAttachmentResponse:
    return RequestAttachmentResponse(
        id=attachment.id,
        request_id=attachment.request_id,
        assignment_id=attachment.assignment_id,
        comment_id=attachment.comment_id,
        uploaded_by_type=attachment.uploaded_by_type if attachment.uploaded_by_type == RequestHistoryActorType.CONTRACTOR_USER else RequestHistoryActorType.SYSTEM,
        uploaded_by_id=attachment.uploaded_by_id if attachment.uploaded_by_type == RequestHistoryActorType.CONTRACTOR_USER else None,
        contractor_id=attachment.contractor_id if attachment.uploaded_by_type == RequestHistoryActorType.CONTRACTOR_USER else None,
        category=attachment.category,
        visibility=attachment.visibility,
        original_filename=attachment.original_filename,
        mime_type=attachment.mime_type,
        size_bytes=attachment.size_bytes,
        checksum_sha256=attachment.checksum_sha256,
        created_at=attachment.created_at,
        is_deleted=attachment.is_deleted,
    )


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
        if item.changed_fields and item.changed_fields.get("visibility", {}).get("new") == RequestVisibility.INTERNAL.value:
            continue
        changed_fields = None
        if item.changed_fields and "assignment_status" in item.changed_fields:
            changed_fields = {"assignment_status": item.changed_fields["assignment_status"]}
        elif item.changed_fields and "attachment_id" in item.changed_fields:
            changed_fields = {
                key: item.changed_fields[key]
                for key in ("attachment_id", "category", "original_filename", "size_bytes")
                if key in item.changed_fields
            }
        elif item.changed_fields and "comment_id" in item.changed_fields:
            changed_fields = {"comment_id": item.changed_fields["comment_id"], "visibility": item.changed_fields.get("visibility")}
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


@router.get("/requests/{request_id}/comments", response_model=list[RequestCommentResponse], summary="List contractor-visible comments")
def list_contractor_request_comments(
    request_id: UUID,
    db: Session = Depends(get_db),
    contractor_id: UUID = Depends(get_current_contractor_id),
) -> list[RequestCommentResponse]:
    ensure_contractor_exists(db, contractor_id)
    request = get_owned_request(db, request_id, contractor_id)
    return [serialize_contractor_comment(comment) for comment in list_contractor_comments(db, request)]


@router.post("/requests/{request_id}/comments", response_model=RequestCommentResponse, status_code=status.HTTP_201_CREATED, summary="Create contractor comment")
def create_contractor_request_comment(
    request_id: UUID,
    payload: RequestCommentCreate,
    db: Session = Depends(get_db),
    contractor_id: UUID = Depends(get_current_contractor_id),
) -> RequestCommentResponse:
    ensure_contractor_exists(db, contractor_id)
    request = get_owned_request(db, request_id, contractor_id)
    return serialize_contractor_comment(create_contractor_comment(db, request, payload, contractor_id))


@router.patch("/requests/{request_id}/comments/{comment_id}", response_model=RequestCommentResponse, summary="Update contractor comment")
def update_contractor_request_comment(
    request_id: UUID,
    comment_id: UUID,
    payload: RequestCommentUpdate,
    db: Session = Depends(get_db),
    contractor_id: UUID = Depends(get_current_contractor_id),
) -> RequestCommentResponse:
    ensure_contractor_exists(db, contractor_id)
    request = get_owned_request(db, request_id, contractor_id)
    comment = get_comment_or_404(db, request_id, comment_id)
    return serialize_contractor_comment(update_comment(db, request, comment, payload, RequestHistoryActorType.CONTRACTOR_USER, contractor_id, contractor_id=contractor_id))


@router.delete("/requests/{request_id}/comments/{comment_id}", response_model=RequestCommentResponse, summary="Delete contractor comment")
def delete_contractor_request_comment(
    request_id: UUID,
    comment_id: UUID,
    db: Session = Depends(get_db),
    contractor_id: UUID = Depends(get_current_contractor_id),
) -> RequestCommentResponse:
    ensure_contractor_exists(db, contractor_id)
    request = get_owned_request(db, request_id, contractor_id)
    comment = get_comment_or_404(db, request_id, comment_id)
    return serialize_contractor_comment(delete_comment(db, request, comment, RequestHistoryActorType.CONTRACTOR_USER, contractor_id, contractor_id=contractor_id))


@router.get("/requests/{request_id}/attachments", response_model=list[RequestAttachmentResponse], summary="List contractor-visible attachments")
def list_contractor_request_attachments(
    request_id: UUID,
    db: Session = Depends(get_db),
    contractor_id: UUID = Depends(get_current_contractor_id),
) -> list[RequestAttachmentResponse]:
    ensure_contractor_exists(db, contractor_id)
    request = get_owned_request(db, request_id, contractor_id)
    return [serialize_contractor_attachment(attachment) for attachment in list_contractor_attachments(db, request)]


@router.post("/requests/{request_id}/attachments", response_model=RequestAttachmentResponse, status_code=status.HTTP_201_CREATED, summary="Upload contractor attachment")
async def upload_contractor_request_attachment(
    request_id: UUID,
    file: UploadFile = File(...),
    category: RequestAttachmentCategory = Form(...),
    visibility: RequestVisibility = Form(RequestVisibility.SHARED),
    assignment_id: UUID | None = Form(default=None),
    comment_id: UUID | None = Form(default=None),
    db: Session = Depends(get_db),
    contractor_id: UUID = Depends(get_current_contractor_id),
) -> RequestAttachmentResponse:
    ensure_contractor_exists(db, contractor_id)
    request = get_owned_request(db, request_id, contractor_id)
    attachment = await create_attachment(
        db,
        request,
        file,
        category,
        visibility,
        RequestHistoryActorType.CONTRACTOR_USER,
        contractor_id,
        contractor_id,
        assignment_id,
        comment_id,
    )
    return serialize_contractor_attachment(attachment)


@router.get("/requests/{request_id}/attachments/{attachment_id}/download", summary="Download contractor-visible attachment")
def download_contractor_request_attachment(
    request_id: UUID,
    attachment_id: UUID,
    db: Session = Depends(get_db),
    contractor_id: UUID = Depends(get_current_contractor_id),
) -> FileResponse:
    ensure_contractor_exists(db, contractor_id)
    get_owned_request(db, request_id, contractor_id)
    attachment = get_attachment_or_404(db, request_id, attachment_id)
    ensure_contractor_can_access_attachment(attachment)
    return FileResponse(attachment_file_path(attachment), media_type=attachment.mime_type, filename=attachment.original_filename)


@router.delete("/requests/{request_id}/attachments/{attachment_id}", response_model=RequestAttachmentResponse, summary="Delete contractor attachment")
def delete_contractor_request_attachment(
    request_id: UUID,
    attachment_id: UUID,
    db: Session = Depends(get_db),
    contractor_id: UUID = Depends(get_current_contractor_id),
) -> RequestAttachmentResponse:
    ensure_contractor_exists(db, contractor_id)
    request = get_owned_request(db, request_id, contractor_id)
    attachment = get_attachment_or_404(db, request_id, attachment_id)
    ensure_contractor_can_access_attachment(attachment)
    if attachment.contractor_id != contractor_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    return serialize_contractor_attachment(delete_attachment(db, request, attachment, RequestHistoryActorType.CONTRACTOR_USER, contractor_id))
