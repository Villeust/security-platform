from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import ContractorAuthContext, require_contractor_permission, require_csrf
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
from app.schemas.contractor_portal import ContractorCompany, ContractorDashboardResponse, ContractorMeResponse, ContractorNotificationResponse
from app.services.request_service import change_assignment_status
from app.services.attachment_service import (
    attachment_download_response,
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

router = APIRouter(prefix="/contractor", tags=["contractor portal"], dependencies=[Depends(require_csrf)])

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
    contractor_ids: set[UUID],
) -> ContractorRequestListResponse:
    own_assignments = [
        ContractorAssignmentResponse.model_validate(assignment)
        for assignment in request.assignments
        if assignment.contractor_id in contractor_ids
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
        work_type_ids=[assignment.work_type_id for assignment in request.assignments if assignment.contractor_id in contractor_ids],
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


def get_owned_request(db: Session, request_id: UUID, contractor_ids: set[UUID]) -> ContractorRequest:
    request = db.scalar(
        select(ContractorRequest)
        .join(RequestAssignment)
        .where(ContractorRequest.id == request_id, RequestAssignment.contractor_id.in_(contractor_ids))
        .options(selectinload(ContractorRequest.assignments), selectinload(ContractorRequest.work_types))
    )
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return request


def contractor_id_for_request(request: ContractorRequest, context: ContractorAuthContext) -> UUID:
    for assignment in request.assignments:
        if assignment.contractor_id in context.contractor_ids:
            return assignment.contractor_id
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contractor context not found")


def serialize_me(context: ContractorAuthContext) -> ContractorMeResponse:
    if context.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User context is required")
    companies = [
        ContractorCompany(
            id=membership.contractor_id,
            name=membership.contractor.name,
            code=membership.contractor.code,
            is_primary=membership.is_primary,
        )
        for membership in context.user.contractor_memberships
        if membership.contractor_id in context.contractor_ids and membership.contractor is not None
    ]
    return ContractorMeResponse(
        user_id=context.user.id,
        username=context.user.username,
        display_name=context.user.display_name,
        email=context.user.email,
        roles=sorted(context.roles or []),
        permissions=sorted(context.permissions or []),
        primary_contractor_id=context.primary_contractor_id,
        contractors=companies,
    )


@router.get("/me", response_model=ContractorMeResponse, summary="Get current contractor portal context")
def get_contractor_me(
    context: ContractorAuthContext = Depends(require_contractor_permission("contractor.portal.view")),
) -> ContractorMeResponse:
    return serialize_me(context)


@router.get("/profile", response_model=ContractorMeResponse, summary="Get contractor profile")
def get_contractor_profile(
    context: ContractorAuthContext = Depends(require_contractor_permission("contractor.profile.view")),
) -> ContractorMeResponse:
    return serialize_me(context)


@router.get("/dashboard", response_model=ContractorDashboardResponse, summary="Get contractor dashboard")
def get_contractor_dashboard(
    db: Session = Depends(get_db),
    context: ContractorAuthContext = Depends(require_contractor_permission("contractor.dashboard.view")),
) -> ContractorDashboardResponse:
    assignments = list(
        db.scalars(
            select(RequestAssignment)
            .where(RequestAssignment.contractor_id.in_(context.contractor_ids))
            .options(selectinload(RequestAssignment.request).selectinload(ContractorRequest.assignments))
        ).all()
    )
    latest = list(
        db.scalars(
            select(ContractorRequest)
            .join(RequestAssignment)
            .where(RequestAssignment.contractor_id.in_(context.contractor_ids))
            .options(selectinload(ContractorRequest.assignments), selectinload(ContractorRequest.work_types))
            .order_by(ContractorRequest.created_at.desc())
            .limit(5)
        ).unique().all()
    )
    active_statuses = {AssignmentStatus.ASSIGNED, AssignmentStatus.ACCEPTED, AssignmentStatus.IN_PROGRESS}
    return ContractorDashboardResponse(
        active_requests=len({assignment.request_id for assignment in assignments if assignment.status in active_statuses}),
        assigned_tasks=sum(1 for assignment in assignments if assignment.status == AssignmentStatus.ASSIGNED),
        in_progress_tasks=sum(1 for assignment in assignments if assignment.status in {AssignmentStatus.ACCEPTED, AssignmentStatus.IN_PROGRESS}),
        completed_tasks=sum(1 for assignment in assignments if assignment.status == AssignmentStatus.COMPLETED),
        latest_requests=[serialize_contractor_request(item, context.contractor_ids).model_dump(mode="json") for item in latest],
    )


@router.get("/notifications", response_model=list[ContractorNotificationResponse], summary="List contractor notifications")
def list_contractor_notifications(
    _: ContractorAuthContext = Depends(require_contractor_permission("contractor.notifications.view")),
) -> list[ContractorNotificationResponse]:
    return []


@router.get(
    "/requests",
    response_model=list[ContractorRequestListResponse],
    summary="List contractor-visible requests",
)
def list_contractor_requests(
    request_status: RequestStatus | None = Query(default=None, alias="status"),
    assignment_status: AssignmentStatus | None = Query(default=None),
    search: str | None = Query(default=None, max_length=128),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    context: ContractorAuthContext = Depends(require_contractor_permission("contractor.requests.view")),
) -> list[ContractorRequestListResponse]:
    statement = (
        select(ContractorRequest)
        .join(RequestAssignment)
        .where(RequestAssignment.contractor_id.in_(context.contractor_ids))
        .options(selectinload(ContractorRequest.assignments), selectinload(ContractorRequest.work_types))
    )
    if request_status is not None:
        statement = statement.where(ContractorRequest.status == request_status)
    if assignment_status is not None:
        statement = statement.where(RequestAssignment.status == assignment_status)
    if search:
        like = f"%{search}%"
        statement = statement.where(ContractorRequest.title.ilike(like) | ContractorRequest.request_number.ilike(like))
    requests = db.scalars(statement.order_by(ContractorRequest.created_at.desc()).offset(skip).limit(limit)).unique().all()
    return [serialize_contractor_request(request, context.contractor_ids) for request in requests]


@router.get("/tasks", response_model=list[ContractorAssignmentResponse], summary="List current contractor tasks")
def list_contractor_tasks(
    assignment_status: AssignmentStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    context: ContractorAuthContext = Depends(require_contractor_permission("contractor.requests.view")),
) -> list[ContractorAssignmentResponse]:
    statement = select(RequestAssignment).where(RequestAssignment.contractor_id.in_(context.contractor_ids))
    if assignment_status is not None:
        statement = statement.where(RequestAssignment.status == assignment_status)
    assignments = db.scalars(statement.order_by(RequestAssignment.updated_at.desc()).offset(skip).limit(limit)).all()
    return [ContractorAssignmentResponse.model_validate(assignment) for assignment in assignments]


@router.get("/requests/{request_id}", response_model=ContractorRequestListResponse, summary="Get contractor-visible request")
def get_contractor_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    context: ContractorAuthContext = Depends(require_contractor_permission("contractor.requests.view")),
) -> ContractorRequestListResponse:
    return serialize_contractor_request(get_owned_request(db, request_id, context.contractor_ids), context.contractor_ids)


@router.post("/requests/{request_id}/accept", response_model=ContractorRequestListResponse, summary="Accept request assignments")
def accept_contractor_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
    context: ContractorAuthContext = Depends(require_contractor_permission("contractor.requests.accept")),
) -> ContractorRequestListResponse:
    request = get_owned_request(db, request_id, context.contractor_ids)
    for assignment in request.assignments:
        if assignment.contractor_id in context.contractor_ids and assignment.status == AssignmentStatus.ASSIGNED:
            change_assignment_status(
                db,
                assignment,
                AssignmentStatus.ACCEPTED,
                actor_type=RequestHistoryActorType.CONTRACTOR_USER,
                actor_id=context.actor_id,
                commit=False,
            )
    db.commit()
    return serialize_contractor_request(get_owned_request(db, request_id, context.contractor_ids), context.contractor_ids)


@router.post(
    "/assignments/{assignment_id}/status",
    response_model=ContractorAssignmentResponse,
    summary="Update own assignment status",
)
def update_assignment_status(
    assignment_id: UUID,
    payload: AssignmentStatusUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
    context: ContractorAuthContext = Depends(require_contractor_permission("contractor.requests.update_status")),
) -> ContractorAssignmentResponse:
    assignment = db.scalar(
        select(RequestAssignment)
        .where(
            RequestAssignment.id == assignment_id,
            RequestAssignment.contractor_id.in_(context.contractor_ids),
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
        actor_id=context.actor_id,
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
    context: ContractorAuthContext = Depends(require_contractor_permission("contractor.requests.view")),
) -> list[RequestHistoryItem]:
    get_owned_request(db, request_id, context.contractor_ids)
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
    context: ContractorAuthContext = Depends(require_contractor_permission("contractor.requests.view")),
) -> list[RequestCommentResponse]:
    request = get_owned_request(db, request_id, context.contractor_ids)
    return [serialize_contractor_comment(comment) for comment in list_contractor_comments(db, request)]


@router.post("/requests/{request_id}/comments", response_model=RequestCommentResponse, status_code=status.HTTP_201_CREATED, summary="Create contractor comment")
def create_contractor_request_comment(
    request_id: UUID,
    payload: RequestCommentCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
    context: ContractorAuthContext = Depends(require_contractor_permission("contractor.comments.create")),
) -> RequestCommentResponse:
    request = get_owned_request(db, request_id, context.contractor_ids)
    contractor_id = contractor_id_for_request(request, context)
    return serialize_contractor_comment(create_contractor_comment(db, request, payload, contractor_id))


@router.patch("/requests/{request_id}/comments/{comment_id}", response_model=RequestCommentResponse, summary="Update contractor comment")
def update_contractor_request_comment(
    request_id: UUID,
    comment_id: UUID,
    payload: RequestCommentUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
    context: ContractorAuthContext = Depends(require_contractor_permission("contractor.comments.update_own")),
) -> RequestCommentResponse:
    request = get_owned_request(db, request_id, context.contractor_ids)
    contractor_id = contractor_id_for_request(request, context)
    comment = get_comment_or_404(db, request_id, comment_id)
    return serialize_contractor_comment(update_comment(db, request, comment, payload, RequestHistoryActorType.CONTRACTOR_USER, contractor_id, contractor_id=contractor_id))


@router.delete("/requests/{request_id}/comments/{comment_id}", response_model=RequestCommentResponse, summary="Delete contractor comment")
def delete_contractor_request_comment(
    request_id: UUID,
    comment_id: UUID,
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
    context: ContractorAuthContext = Depends(require_contractor_permission("contractor.comments.delete_own")),
) -> RequestCommentResponse:
    request = get_owned_request(db, request_id, context.contractor_ids)
    contractor_id = contractor_id_for_request(request, context)
    comment = get_comment_or_404(db, request_id, comment_id)
    return serialize_contractor_comment(delete_comment(db, request, comment, RequestHistoryActorType.CONTRACTOR_USER, contractor_id, contractor_id=contractor_id))


@router.get("/requests/{request_id}/attachments", response_model=list[RequestAttachmentResponse], summary="List contractor-visible attachments")
def list_contractor_request_attachments(
    request_id: UUID,
    db: Session = Depends(get_db),
    context: ContractorAuthContext = Depends(require_contractor_permission("contractor.requests.view")),
) -> list[RequestAttachmentResponse]:
    request = get_owned_request(db, request_id, context.contractor_ids)
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
    _: None = Depends(require_csrf),
    context: ContractorAuthContext = Depends(require_contractor_permission("contractor.attachments.upload")),
) -> RequestAttachmentResponse:
    request = get_owned_request(db, request_id, context.contractor_ids)
    contractor_id = contractor_id_for_request(request, context)
    attachment = await create_attachment(
        db,
        request,
        file,
        category,
        visibility,
        RequestHistoryActorType.CONTRACTOR_USER,
        context.actor_id,
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
    context: ContractorAuthContext = Depends(require_contractor_permission("contractor.requests.view")),
) -> FileResponse:
    get_owned_request(db, request_id, context.contractor_ids)
    attachment = get_attachment_or_404(db, request_id, attachment_id)
    ensure_contractor_can_access_attachment(attachment)
    return attachment_download_response(attachment)


@router.delete("/requests/{request_id}/attachments/{attachment_id}", response_model=RequestAttachmentResponse, summary="Delete contractor attachment")
def delete_contractor_request_attachment(
    request_id: UUID,
    attachment_id: UUID,
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
    context: ContractorAuthContext = Depends(require_contractor_permission("contractor.attachments.delete_own")),
) -> RequestAttachmentResponse:
    request = get_owned_request(db, request_id, context.contractor_ids)
    attachment = get_attachment_or_404(db, request_id, attachment_id)
    ensure_contractor_can_access_attachment(attachment)
    if attachment.contractor_id not in context.contractor_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    return serialize_contractor_attachment(delete_attachment(db, request, attachment, RequestHistoryActorType.CONTRACTOR_USER, context.actor_id))
