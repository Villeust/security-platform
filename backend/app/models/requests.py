from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.reference_data import Contractor, Facility, Premise, TimestampMixin, WorkType, utc_now


class RequestStatus(StrEnum):
    DRAFT = "DRAFT"
    NEW = "NEW"
    PARTIALLY_ASSIGNED = "PARTIALLY_ASSIGNED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class AssignmentStatus(StrEnum):
    ASSIGNED = "ASSIGNED"
    ACCEPTED = "ACCEPTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class RequestHistoryEventType(StrEnum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    PUBLISHED = "PUBLISHED"
    STATUS_CHANGED = "STATUS_CHANGED"
    ASSIGNMENT_CREATED = "ASSIGNMENT_CREATED"
    ASSIGNMENT_ACCEPTED = "ASSIGNMENT_ACCEPTED"
    ASSIGNMENT_STATUS_CHANGED = "ASSIGNMENT_STATUS_CHANGED"
    REOPENED = "REOPENED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    COMMENT_ADDED = "COMMENT_ADDED"
    COMMENT_UPDATED = "COMMENT_UPDATED"
    COMMENT_DELETED = "COMMENT_DELETED"
    ATTACHMENT_ADDED = "ATTACHMENT_ADDED"
    ATTACHMENT_DELETED = "ATTACHMENT_DELETED"
    WORK_RESULT_ADDED = "WORK_RESULT_ADDED"


class RequestHistoryActorType(StrEnum):
    SYSTEM = "SYSTEM"
    INTERNAL_USER = "INTERNAL_USER"
    CONTRACTOR_USER = "CONTRACTOR_USER"


class RequestVisibility(StrEnum):
    SHARED = "SHARED"
    INTERNAL = "INTERNAL"


class RequestAttachmentCategory(StrEnum):
    REQUEST_FILE = "REQUEST_FILE"
    WORK_RESULT = "WORK_RESULT"
    ACT = "ACT"
    PHOTO = "PHOTO"
    DOCUMENT = "DOCUMENT"
    OTHER = "OTHER"


class ContractorRequest(TimestampMixin, Base):
    __tablename__ = "contractor_requests"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    request_number: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    city_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("cities.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    facility_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("facilities.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    premise_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("premises.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(32), nullable=True)
    desired_completion_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, name="request_status"),
        nullable=False,
        default=RequestStatus.DRAFT,
    )

    facility: Mapped[Facility | None] = relationship()
    premise: Mapped[Premise | None] = relationship()
    work_types: Mapped[list["RequestWorkType"]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
    )
    assignments: Mapped[list["RequestAssignment"]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
    )
    history: Mapped[list["RequestHistory"]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
        order_by="RequestHistory.created_at",
    )
    comments: Mapped[list["RequestComment"]] = relationship(back_populates="request", cascade="all, delete-orphan")
    attachments: Mapped[list["RequestAttachment"]] = relationship(back_populates="request", cascade="all, delete-orphan")


class RequestWorkType(Base):
    __tablename__ = "request_work_types"
    __table_args__ = (
        UniqueConstraint("request_id", "work_type_id", name="uq_request_work_type"),
    )

    request_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("contractor_requests.id", ondelete="CASCADE"),
        primary_key=True,
    )
    work_type_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("work_types.id", ondelete="RESTRICT"),
        primary_key=True,
    )

    request: Mapped[ContractorRequest] = relationship(back_populates="work_types")
    work_type: Mapped[WorkType] = relationship()


class RequestAssignment(TimestampMixin, Base):
    __tablename__ = "request_assignments"
    __table_args__ = (
        UniqueConstraint("request_id", "work_type_id", name="uq_request_assignment_work_type"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    request_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("contractor_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contractor_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("contractors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    work_type_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("work_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus, name="assignment_status"),
        nullable=False,
        default=AssignmentStatus.ASSIGNED,
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    request: Mapped[ContractorRequest] = relationship(back_populates="assignments")
    contractor: Mapped[Contractor] = relationship()
    work_type: Mapped[WorkType] = relationship()
    attachments: Mapped[list["RequestAttachment"]] = relationship(back_populates="assignment")


class ContractorUser(Base):
    __tablename__ = "contractor_users"
    __table_args__ = (
        UniqueConstraint("user_id", "contractor_id", name="uq_contractor_user"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    contractor_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("contractors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    contractor: Mapped[Contractor] = relationship()


class RequestHistory(Base):
    __tablename__ = "request_history"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    request_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("contractor_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[RequestHistoryEventType] = mapped_column(
        Enum(RequestHistoryEventType, name="request_history_event_type"),
        nullable=False,
    )
    old_status: Mapped[RequestStatus | None] = mapped_column(Enum(RequestStatus, name="request_status"), nullable=True)
    new_status: Mapped[RequestStatus | None] = mapped_column(Enum(RequestStatus, name="request_status"), nullable=True)
    changed_fields: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    actor_type: Mapped[RequestHistoryActorType] = mapped_column(
        Enum(RequestHistoryActorType, name="request_history_actor_type"),
        nullable=False,
    )
    actor_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    request: Mapped[ContractorRequest] = relationship(back_populates="history")


class RequestComment(TimestampMixin, Base):
    __tablename__ = "request_comments"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    request_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("contractor_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_type: Mapped[RequestHistoryActorType] = mapped_column(
        Enum(RequestHistoryActorType, name="request_history_actor_type"),
        nullable=False,
    )
    author_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    contractor_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("contractors.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    visibility: Mapped[RequestVisibility] = mapped_column(Enum(RequestVisibility, name="request_visibility"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_edited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    request: Mapped[ContractorRequest] = relationship(back_populates="comments")
    contractor: Mapped[Contractor | None] = relationship()
    attachments: Mapped[list["RequestAttachment"]] = relationship(back_populates="comment")


class RequestAttachment(Base):
    __tablename__ = "request_attachments"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    request_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("contractor_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assignment_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("request_assignments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    comment_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("request_comments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    uploaded_by_type: Mapped[RequestHistoryActorType] = mapped_column(
        Enum(RequestHistoryActorType, name="request_history_actor_type"),
        nullable=False,
    )
    uploaded_by_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    contractor_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("contractors.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    category: Mapped[RequestAttachmentCategory] = mapped_column(
        Enum(RequestAttachmentCategory, name="request_attachment_category"),
        nullable=False,
    )
    visibility: Mapped[RequestVisibility] = mapped_column(Enum(RequestVisibility, name="request_visibility"), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    request: Mapped[ContractorRequest] = relationship(back_populates="attachments")
    assignment: Mapped[RequestAssignment | None] = relationship(back_populates="attachments")
    comment: Mapped[RequestComment | None] = relationship(back_populates="attachments")
    contractor: Mapped[Contractor | None] = relationship()
