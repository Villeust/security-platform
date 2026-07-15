from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.requests import (
    ContractorRequest,
    RequestComment,
    RequestHistoryActorType,
    RequestHistoryEventType,
    RequestVisibility,
)
from app.schemas.collaboration import RequestCommentCreate, RequestCommentUpdate
from app.services.request_service import add_history

DELETED_COMMENT_BODY = "Комментарий удалён"


def serialize_comment_body(comment: RequestComment) -> str:
    return DELETED_COMMENT_BODY if comment.is_deleted else comment.body


def get_comment_or_404(db: Session, request_id: UUID, comment_id: UUID) -> RequestComment:
    comment = db.scalar(select(RequestComment).where(RequestComment.id == comment_id, RequestComment.request_id == request_id))
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    return comment


def list_internal_comments(db: Session, request: ContractorRequest) -> list[RequestComment]:
    return list(db.scalars(select(RequestComment).where(RequestComment.request_id == request.id).order_by(RequestComment.created_at.asc())).all())


def list_contractor_comments(db: Session, request: ContractorRequest) -> list[RequestComment]:
    return list(
        db.scalars(
            select(RequestComment)
            .where(
                RequestComment.request_id == request.id,
                RequestComment.visibility == RequestVisibility.SHARED,
            )
            .order_by(RequestComment.created_at.asc())
        ).all()
    )


def create_internal_comment(
    db: Session,
    request: ContractorRequest,
    payload: RequestCommentCreate,
    actor_id: UUID | None,
) -> RequestComment:
    comment = RequestComment(
        request_id=request.id,
        author_type=RequestHistoryActorType.INTERNAL_USER,
        author_id=actor_id,
        visibility=payload.visibility,
        body=payload.body,
    )
    db.add(comment)
    db.flush()
    add_history(
        request,
        RequestHistoryEventType.COMMENT_ADDED,
        RequestHistoryActorType.INTERNAL_USER,
        actor_id=actor_id,
        changed_fields={"comment_id": {"old": None, "new": str(comment.id)}, "visibility": {"old": None, "new": comment.visibility.value}},
    )
    db.commit()
    db.refresh(comment)
    return comment


def create_contractor_comment(
    db: Session,
    request: ContractorRequest,
    payload: RequestCommentCreate,
    contractor_id: UUID,
) -> RequestComment:
    if payload.visibility != RequestVisibility.SHARED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Contractor comments must be shared")
    comment = RequestComment(
        request_id=request.id,
        author_type=RequestHistoryActorType.CONTRACTOR_USER,
        author_id=contractor_id,
        contractor_id=contractor_id,
        visibility=RequestVisibility.SHARED,
        body=payload.body,
    )
    db.add(comment)
    db.flush()
    add_history(
        request,
        RequestHistoryEventType.COMMENT_ADDED,
        RequestHistoryActorType.CONTRACTOR_USER,
        actor_id=contractor_id,
        changed_fields={"comment_id": {"old": None, "new": str(comment.id)}, "visibility": {"old": None, "new": RequestVisibility.SHARED.value}},
    )
    db.commit()
    db.refresh(comment)
    return comment


def ensure_comment_author(comment: RequestComment, actor_type: RequestHistoryActorType, actor_id: UUID | None, contractor_id: UUID | None = None) -> None:
    if comment.author_type != actor_type:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author can edit this comment")
    expected_id = contractor_id if actor_type == RequestHistoryActorType.CONTRACTOR_USER else actor_id
    if comment.author_id != expected_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author can edit this comment")


def update_comment(
    db: Session,
    request: ContractorRequest,
    comment: RequestComment,
    payload: RequestCommentUpdate,
    actor_type: RequestHistoryActorType,
    actor_id: UUID | None,
    contractor_id: UUID | None = None,
) -> RequestComment:
    ensure_comment_author(comment, actor_type, actor_id, contractor_id)
    if comment.is_deleted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Deleted comment cannot be edited")
    old_body = comment.body
    comment.body = payload.body
    comment.is_edited = True
    add_history(
        request,
        RequestHistoryEventType.COMMENT_UPDATED,
        actor_type,
        actor_id=contractor_id if actor_type == RequestHistoryActorType.CONTRACTOR_USER else actor_id,
        changed_fields={"comment_id": {"old": None, "new": str(comment.id)}, "visibility": {"old": None, "new": comment.visibility.value}},
        comment="Comment updated" if old_body != payload.body else None,
    )
    db.commit()
    db.refresh(comment)
    return comment


def delete_comment(
    db: Session,
    request: ContractorRequest,
    comment: RequestComment,
    actor_type: RequestHistoryActorType,
    actor_id: UUID | None,
    contractor_id: UUID | None = None,
) -> RequestComment:
    ensure_comment_author(comment, actor_type, actor_id, contractor_id)
    comment.is_deleted = True
    add_history(
        request,
        RequestHistoryEventType.COMMENT_DELETED,
        actor_type,
        actor_id=contractor_id if actor_type == RequestHistoryActorType.CONTRACTOR_USER else actor_id,
        changed_fields={"comment_id": {"old": None, "new": str(comment.id)}, "visibility": {"old": None, "new": comment.visibility.value}},
    )
    db.commit()
    db.refresh(comment)
    return comment
