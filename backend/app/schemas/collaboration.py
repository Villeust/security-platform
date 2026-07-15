from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.requests import RequestAttachmentCategory, RequestHistoryActorType, RequestVisibility


class RequestCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    visibility: RequestVisibility = RequestVisibility.SHARED

    @field_validator("body")
    @classmethod
    def validate_body(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Comment body cannot be empty")
        return value


class RequestCommentUpdate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)

    @field_validator("body")
    @classmethod
    def validate_body(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Comment body cannot be empty")
        return value


class RequestCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_id: UUID
    author_type: RequestHistoryActorType
    author_id: UUID | None
    contractor_id: UUID | None
    visibility: RequestVisibility
    body: str
    created_at: datetime
    updated_at: datetime
    is_edited: bool
    is_deleted: bool


class RequestAttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_id: UUID
    assignment_id: UUID | None
    comment_id: UUID | None
    uploaded_by_type: RequestHistoryActorType
    uploaded_by_id: UUID | None
    contractor_id: UUID | None
    category: RequestAttachmentCategory
    visibility: RequestVisibility
    original_filename: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    created_at: datetime
    is_deleted: bool
