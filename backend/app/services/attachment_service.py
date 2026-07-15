from hashlib import sha256
from pathlib import Path, PurePath
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.requests import (
    ContractorRequest,
    RequestAssignment,
    RequestAttachment,
    RequestAttachmentCategory,
    RequestHistoryActorType,
    RequestHistoryEventType,
    RequestVisibility,
)
from app.services.request_service import add_history

MAX_ATTACHMENT_SIZE_BYTES = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf", "doc", "docx", "xls", "xlsx", "txt", "zip"}
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
    "application/zip",
    "application/x-zip-compressed",
}


def storage_root() -> Path:
    root = Path(settings.storage_root)
    if not root.is_absolute():
        root = Path.cwd() / root
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def validate_original_filename(filename: str | None) -> tuple[str, str]:
    if not filename:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Filename is required")
    pure = PurePath(filename)
    if pure.name != filename or ".." in pure.parts:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Invalid filename")
    extension = pure.suffix.lower().lstrip(".")
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="File extension is not allowed")
    return pure.name, extension


def validate_mime_type(mime_type: str | None) -> str:
    if not mime_type or mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="File MIME type is not allowed")
    return mime_type


def ensure_assignment_scope(
    db: Session,
    request: ContractorRequest,
    assignment_id: UUID | None,
    category: RequestAttachmentCategory,
    contractor_id: UUID | None = None,
) -> RequestAssignment | None:
    if category == RequestAttachmentCategory.WORK_RESULT and assignment_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="assignment_id is required for WORK_RESULT")
    if assignment_id is None:
        return None
    assignment = db.scalar(select(RequestAssignment).where(RequestAssignment.id == assignment_id, RequestAssignment.request_id == request.id))
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    if contractor_id is not None and assignment.contractor_id != contractor_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    return assignment


def ensure_comment_scope(db: Session, request: ContractorRequest, comment_id: UUID | None) -> None:
    if comment_id is None:
        return
    from app.models.requests import RequestComment

    comment = db.scalar(select(RequestComment).where(RequestComment.id == comment_id, RequestComment.request_id == request.id))
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")


async def save_upload_to_storage(request: ContractorRequest, attachment_id: UUID, extension: str, upload: UploadFile) -> tuple[str, str, int, str]:
    root = storage_root()
    stored_filename = f"{uuid4().hex}.{extension}"
    target_dir = (root / "requests" / str(request.id) / str(attachment_id)).resolve()
    target_path = (target_dir / stored_filename).resolve()
    if not str(target_path).startswith(str(root)):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Invalid storage path")
    target_dir.mkdir(parents=True, exist_ok=True)

    digest = sha256()
    size = 0
    with target_path.open("wb") as destination:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_ATTACHMENT_SIZE_BYTES:
                destination.close()
                target_path.unlink(missing_ok=True)
                raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File is too large")
            digest.update(chunk)
            destination.write(chunk)
    return stored_filename, str(target_path.relative_to(root)), size, digest.hexdigest()


def get_attachment_or_404(db: Session, request_id: UUID, attachment_id: UUID) -> RequestAttachment:
    attachment = db.scalar(select(RequestAttachment).where(RequestAttachment.id == attachment_id, RequestAttachment.request_id == request_id))
    if attachment is None or attachment.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    return attachment


def list_internal_attachments(db: Session, request: ContractorRequest) -> list[RequestAttachment]:
    return list(db.scalars(select(RequestAttachment).where(RequestAttachment.request_id == request.id, RequestAttachment.is_deleted.is_(False)).order_by(RequestAttachment.created_at.asc())).all())


def list_contractor_attachments(db: Session, request: ContractorRequest) -> list[RequestAttachment]:
    return list(
        db.scalars(
            select(RequestAttachment)
            .where(
                RequestAttachment.request_id == request.id,
                RequestAttachment.visibility == RequestVisibility.SHARED,
                RequestAttachment.is_deleted.is_(False),
            )
            .order_by(RequestAttachment.created_at.asc())
        ).all()
    )


async def create_attachment(
    db: Session,
    request: ContractorRequest,
    upload: UploadFile,
    category: RequestAttachmentCategory,
    visibility: RequestVisibility,
    uploaded_by_type: RequestHistoryActorType,
    uploaded_by_id: UUID | None,
    contractor_id: UUID | None,
    assignment_id: UUID | None,
    comment_id: UUID | None,
) -> RequestAttachment:
    if uploaded_by_type == RequestHistoryActorType.CONTRACTOR_USER and visibility != RequestVisibility.SHARED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Contractor attachments must be shared")
    original_filename, extension = validate_original_filename(upload.filename)
    mime_type = validate_mime_type(upload.content_type)
    ensure_assignment_scope(db, request, assignment_id, category, contractor_id if uploaded_by_type == RequestHistoryActorType.CONTRACTOR_USER else None)
    ensure_comment_scope(db, request, comment_id)

    attachment_id = uuid4()
    stored_filename, relative_storage_path, size, checksum = await save_upload_to_storage(request, attachment_id, extension, upload)
    attachment = RequestAttachment(
        id=attachment_id,
        request_id=request.id,
        assignment_id=assignment_id,
        comment_id=comment_id,
        uploaded_by_type=uploaded_by_type,
        uploaded_by_id=uploaded_by_id,
        contractor_id=contractor_id,
        category=category,
        visibility=visibility,
        original_filename=original_filename,
        stored_filename=stored_filename,
        storage_path=relative_storage_path,
        mime_type=mime_type,
        size_bytes=size,
        checksum_sha256=checksum,
    )
    db.add(attachment)
    event_type = RequestHistoryEventType.WORK_RESULT_ADDED if category == RequestAttachmentCategory.WORK_RESULT else RequestHistoryEventType.ATTACHMENT_ADDED
    add_history(
        request,
        event_type,
        uploaded_by_type,
        actor_id=uploaded_by_id,
        changed_fields={
            "attachment_id": {"old": None, "new": str(attachment.id)},
            "category": {"old": None, "new": category.value},
            "original_filename": {"old": None, "new": original_filename},
            "size_bytes": {"old": None, "new": size},
            "visibility": {"old": None, "new": visibility.value},
        },
    )
    db.commit()
    db.refresh(attachment)
    return attachment


def attachment_file_path(attachment: RequestAttachment) -> Path:
    root = storage_root()
    path = (root / attachment.storage_path).resolve()
    if not str(path).startswith(str(root)) or not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment file not found")
    return path


def ensure_contractor_can_access_attachment(attachment: RequestAttachment) -> None:
    if attachment.visibility != RequestVisibility.SHARED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")


def delete_attachment(
    db: Session,
    request: ContractorRequest,
    attachment: RequestAttachment,
    actor_type: RequestHistoryActorType,
    actor_id: UUID | None,
) -> RequestAttachment:
    attachment.is_deleted = True
    add_history(
        request,
        RequestHistoryEventType.ATTACHMENT_DELETED,
        actor_type,
        actor_id=actor_id,
        changed_fields={
            "attachment_id": {"old": None, "new": str(attachment.id)},
            "category": {"old": None, "new": attachment.category.value},
            "original_filename": {"old": None, "new": attachment.original_filename},
            "size_bytes": {"old": None, "new": attachment.size_bytes},
            "visibility": {"old": None, "new": attachment.visibility.value},
        },
    )
    db.commit()
    db.refresh(attachment)
    return attachment
